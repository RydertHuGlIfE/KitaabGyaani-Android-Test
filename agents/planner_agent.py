import json
import os
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List

from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService
from services.planner_service import (
    get_credentials,
    get_calendar_service,
    get_primary_timezone,
    fetch_busy_intervals,
    find_free_study_slots,
    insert_study_sessions
)

class PlannerAgent:
    def __init__(self, llm_service: LLMService, ocr_service: OCRService, pdf_service: PDFService):
        self.llm = llm_service
        self.ocr = ocr_service
        self.pdf = pdf_service

    async def generate_schedule(
        self, exam_name: str, exam_date: str, topics_completed: list, syllabus: list,
        content: str = None, is_image: bool = False, start_date: str = None
    ) -> dict:
        # 1. Parse syllabus from optional files
        extracted_syllabus = ""
        if content:
            cleaned_content = content
            if "," in content:
                cleaned_content = content.split(",")[1]
            is_pdf = cleaned_content.startswith("JVBERi")
            if is_pdf:
                extracted_syllabus = self.pdf.extract_text(content)
            elif is_image:
                vision_prompt = "Perform OCR on this image. Extract all syllabus topics, schedule details, or planning information from this handwritten or printed document. Output only the extracted list of topics and scheduling content."
                extracted_syllabus = await self.llm.query_vision_llm(cleaned_content, vision_prompt)
            else:
                extracted_syllabus = content

        syllabus_context = json.dumps(syllabus)
        if extracted_syllabus:
            syllabus_context += f"\nAdditional Extracted Syllabus/Schedule details:\n{extracted_syllabus}"

        # 2. Check if Google Calendar is authenticated
        creds = get_credentials()
        if creds:
            try:
                # Agentic Calendar Scheduling path
                current_date_str = date.today().isoformat()
                current_weekday = date.today().strftime("%A")
                
                system_prompt = (
                    "You are an AI Study Scheduler. Your task is to analyze the exam details and return a JSON object containing scheduling parameters.\n"
                    f"Today's date is {current_date_str} ({current_weekday}).\n\n"
                    "Required JSON schema:\n"
                    "{\n"
                    '  "topic": "string (name of subject/exam)",\n'
                    '  "total_sessions": "integer (number of study sessions needed, default 5)",\n'
                    '  "session_duration_hours": "float (hours per session, default 2.0)",\n'
                    '  "start_date": "string (YYYY-MM-DD, default tomorrow)",\n'
                    '  "preferred_start_time": "string (HH:MM, default \'14:00\')",\n'
                    '  "preferred_end_time": "string (HH:MM, default \'18:00\')",\n'
                    '  "excluded_weekdays": "list of integers (0=Monday, 6=Sunday, default [])"\n'
                    "}\n\n"
                    "Return ONLY a valid JSON object. Do not include markdown code block syntax (like ```json)."
                )
                
                prompt = (
                    f"Extract parameters for this study request:\n"
                    f"Exam Name: {exam_name or 'Upcoming Exam'}\n"
                    f"Exam Date: {exam_date or 'TBD'}\n"
                    f"Syllabus Context: {syllabus_context}\n"
                    f"Completed Topics: {json.dumps(topics_completed)}\n"
                )
                
                # Query LLM to parse parameters
                param_text = await self.llm.query_llm(prompt, system_prompt=system_prompt)
                
                # Clean up any surrounding code blocks if returned by the LLM
                param_text = param_text.strip()
                if param_text.startswith("```"):
                    lines = param_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    param_text = "\n".join(lines).strip()
                
                try:
                    params = json.loads(param_text)
                except Exception:
                    # Fallback default parameters
                    params = {
                        "topic": exam_name or "Study Session",
                        "total_sessions": 5,
                        "session_duration_hours": 2.0,
                        "start_date": (date.today() + timedelta(days=1)).isoformat(),
                        "preferred_start_time": "14:00",
                        "preferred_end_time": "18:00",
                        "excluded_weekdays": []
                    }
                
                # Retrieve Calendar Service & Timezone
                service = get_calendar_service(creds)
                tz_str = get_primary_timezone(service)
                
                # Extract values with fallbacks
                topic = params.get("topic") or exam_name or "Study Session"
                total_sessions = int(params.get("total_sessions") or 5)
                session_duration = timedelta(hours=float(params.get("session_duration_hours") or 2.0))
                
                # Prioritize user selected start_date
                start_date_str = start_date or params.get("start_date") or (date.today() + timedelta(days=1)).isoformat()
                start_date = date.fromisoformat(start_date_str)
                window_start_time = time.fromisoformat(params.get("preferred_start_time") or "14:00")
                window_end_time = time.fromisoformat(params.get("preferred_end_time") or "18:00")
                excluded_weekdays = params.get("excluded_weekdays") or []
                if not isinstance(excluded_weekdays, list):
                    excluded_weekdays = []
                
                # Search range: from start_date through the requested exam date when provided.
                start_search_dt = datetime.combine(start_date, time.min).replace(tzinfo=ZoneInfo(tz_str))
                exam_end_date = None
                if exam_date:
                    try:
                        exam_end_date = date.fromisoformat(exam_date)
                    except Exception:
                        exam_end_date = None
                end_search_dt = datetime.combine(exam_end_date, time.max).replace(tzinfo=ZoneInfo(tz_str)) if exam_end_date else start_search_dt + timedelta(days=60)
                
                # Fetch busy intervals
                busy_intervals = fetch_busy_intervals(service, start_search_dt, end_search_dt)
                
                # Find open slots
                slots = find_free_study_slots(
                    start_date=start_date,
                    end_date=exam_end_date,
                    total_sessions=total_sessions,
                    session_duration=session_duration,
                    window_start_time=window_start_time,
                    window_end_time=window_end_time,
                    excluded_weekdays=excluded_weekdays,
                    busy_intervals=busy_intervals,
                    tz_str=tz_str
                )
                
                if slots:
                    created_events = insert_study_sessions(service, topic, slots)
                    
                    schedule_items = []
                    milestones = []
                    for i, (s_dt, e_dt) in enumerate(slots, 1):
                        schedule_items.append({
                            "day": i,
                            "date": s_dt.strftime("%Y-%m-%d"),
                            "topics": [topic],
                            "duration_hours": int(session_duration.total_seconds() // 3600) if session_duration.total_seconds() % 3600 == 0 else round(session_duration.total_seconds() / 3600, 1),
                            "study_load": "high" if i == 1 else "medium" if i < len(slots) else "light",
                            "resources": []
                        })
                        if i == len(slots):
                            milestones.append({
                                "day": i,
                                "milestone": f"Finish {topic} revision"
                            })

                    # Ask LLM to generate the study guide matching the scheduled slots
                    slots_str = "\n".join([
                        f"- Session {i}: {s_dt.strftime('%A, %b %d • %I:%M %p')} - {e_dt.strftime('%I:%M %p')}"
                        for i, (s_dt, e_dt) in enumerate(slots, 1)
                    ])
                    
                    study_prompt = (
                        f"I have successfully scheduled {len(slots)} study sessions in the user's Google Calendar:\n"
                        f"{slots_str}\n\n"
                        f"Please generate a detailed study plan dividing the following syllabus/exam preparation into these specific slots:\n"
                        f"Exam: {exam_name or 'Upcoming Exam'} (Date: {exam_date or 'TBD'})\n"
                        f"Syllabus Context: {syllabus_context}\n"
                        f"Already completed: {json.dumps(topics_completed)}\n\n"
                        "Respond in clear, structured markdown. Detail which topics should be covered in each session."
                    )
                    
                    system_prompt = (
                        "You are a professional Academic Planner. Guide the user through their study schedule, "
                        "mentioning that these slots have been booked in their Google Calendar. Help them understand what to study in each session."
                    )
                    
                    response_text = await self.llm.query_llm(study_prompt, system_prompt=system_prompt)
                    
                    formatted_slots = []
                    for i, (s_dt, e_dt) in enumerate(slots):
                        event_id = created_events[i].get("id") if i < len(created_events) else None
                        formatted_slots.append({
                            "id": event_id,
                            "start": s_dt.isoformat(),
                            "end": e_dt.isoformat(),
                            "formatted": s_dt.strftime("%A, %b %d • %I:%M %p") + " - " + e_dt.strftime("%I:%M %p")
                        })
                        
                    return {
                        "response": response_text,
                        "exam_name": exam_name or "Upcoming Exam",
                        "exam_date": exam_date or "TBD",
                        "schedule": schedule_items,
                        "milestones": milestones
                    }
                else:
                    return {
                        "response": "⚠️ **Conflict Detected**: No free study slots could be found in the preferred study window that avoid your busy times. Please adjust your preferences or clear some events from your calendar!",
                        "exam_name": exam_name or "Upcoming Exam",
                        "exam_date": exam_date or "TBD",
                        "schedule": [],
                        "milestones": []
                    }
            except Exception as e:
                print(f"Error in agentic scheduling: {e}")
                # Fallback to text planning if Google Calendar action fails
                pass

        # 3. Fallback standard text planning path (if no creds or an error occurred)
        system_prompt = (
            "You are a professional Academic Planner. You must follow these safety guardrails strictly:\n"
            "- Only answer educational, academic, or study-related planning queries.\n"
            "- Do not process any inappropriate, sexual, adult, adulterous, violent, or unsafe content.\n"
            "Respond freely in clear, structured markdown. Present a detailed study schedule and milestones for the user.\n"
            "Add a note at the end inviting them to link their Google Calendar for automated, conflict-free slot booking."
        )

        prompt = (
            f"Generate a daily study plan for the exam '{exam_name or 'Upcoming Exam'}' on {exam_date or 'TBD'}.\n"
            f"Syllabus Context: {syllabus_context}\n"
            f"Completed Topics: {json.dumps(topics_completed)}\n"
        )
        
        response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt)
        
        # Append Calendar login CTA
        response_text += (
            "\n\n---\n"
            "🔗 **Google Calendar Integration Available:**\n"
            "Connect your Google Calendar to automatically book conflict-free study slots and sync them straight to your phone!\n"
            "👉 [Connect Google Calendar](http://localhost:8000/login)"
        )
        
        return {
            "response": response_text,
            "exam_name": exam_name or "Upcoming Exam",
            "exam_date": exam_date or "TBD",
            "schedule": [],
            "milestones": []
        }
