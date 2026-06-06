import json
import os
import re
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Tuple

from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService
from services.planner_service import (
    get_credentials,
    get_calendar_service,
    get_primary_timezone,
    fetch_busy_intervals,
    find_free_study_slots,
    insert_study_sessions,
    fetch_all_calendars_busy_intervals
)


def extract_relative_exam_date(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    today = date.today()

    if re.search(r"\bexam\s+(is\s+)?today\b|\btoday\b", lowered):
        return today.isoformat()
    if re.search(r"\bexam\s+(is\s+)?tomorrow\b|\btomorrow\b", lowered):
        return (today + timedelta(days=1)).isoformat()

    match = re.search(r"\b(?:exam|test|paper|deadline)\b.{0,30}?\bin\s+(\d{1,2})\s+days?\b", lowered)
    if not match:
        match = re.search(r"\bin\s+(\d{1,2})\s+days?\b.{0,30}?\b(?:exam|test|paper|deadline)\b", lowered)
    if match:
        return (today + timedelta(days=int(match.group(1)))).isoformat()
    return None


def parse_iso_date_or_none(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


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

        relative_exam_date = extract_relative_exam_date(syllabus_context)
        if relative_exam_date:
            exam_date = relative_exam_date

        # 2. Check if Google Calendar is authenticated
        creds = get_credentials()
        if creds:
            try:
                # Agentic Calendar Scheduling path
                current_date_str = date.today().isoformat()
                current_weekday = date.today().strftime("%A")
                
                # Retrieve Calendar Service & Timezone
                service = get_calendar_service(creds)
                tz_str = get_primary_timezone(service)
                
                # Prioritize user selected start_date
                start_date_str = start_date or (date.today() + timedelta(days=1)).isoformat()
                start_date_obj = date.fromisoformat(start_date_str)
                exam_end_date = parse_iso_date_or_none(exam_date)
                
                # Ensure valid start date range
                if exam_end_date and start_date_obj > exam_end_date:
                    start_date_obj = date.today()
                    if start_date_obj > exam_end_date:
                        start_date_obj = exam_end_date
                    start_date_str = start_date_obj.isoformat()

                # Setup search range
                start_search_dt = datetime.combine(start_date_obj, time.min).replace(tzinfo=ZoneInfo(tz_str))
                end_search_dt = datetime.combine(exam_end_date, time.max).replace(tzinfo=ZoneInfo(tz_str)) if exam_end_date else start_search_dt + timedelta(days=14)
                
                # Fetch busy intervals from all calendars
                raw_busy_intervals = fetch_all_calendars_busy_intervals(service, start_search_dt, end_search_dt)
                
                # Format busy intervals for the LLM
                events_by_day = {}
                for item in raw_busy_intervals:
                    s_dt = item["start"]
                    e_dt = item["end"]
                    if s_dt.tzinfo is not None:
                        s_dt = s_dt.astimezone(ZoneInfo(tz_str))
                    if e_dt.tzinfo is not None:
                        e_dt = e_dt.astimezone(ZoneInfo(tz_str))
                    day_str = s_dt.strftime("%A, %b %d, %Y")
                    time_range = f"{s_dt.strftime('%I:%M %p')} - {e_dt.strftime('%I:%M %p')}"
                    event_desc = f"{time_range}: {item['summary']} (in {item['calendar_summary']})"
                    events_by_day.setdefault(day_str, []).append(event_desc)
                    
                existing_events_str = ""
                for day, events in events_by_day.items():
                    existing_events_str += f"### {day}\n" + "\n".join([f"- {ev}" for ev in events]) + "\n"
                if not existing_events_str:
                    existing_events_str = "No existing calendar events/busy slots found."

                system_prompt = (
                    "You are a highly intelligent AI Study Scheduler.\n"
                    "Your task is to analyze the exam details, the syllabus context, and the user's existing busy calendar events "
                    "to design a customized, conflict-free study schedule. You must place study sessions at optimal times "
                    "(e.g., mornings or afternoons, avoiding late nights and avoiding the user's busy slots).\n\n"
                    f"Today's date is {current_date_str} ({current_weekday}).\n"
                    f"The user's primary timezone is {tz_str}.\n\n"
                    "Required JSON format:\n"
                    "{\n"
                    '  "schedule": [\n'
                    '    {\n'
                    '      "date": "YYYY-MM-DD",\n'
                    '      "start_time": "HH:MM",\n'
                    '      "end_time": "HH:MM",\n'
                    '      "topic": "specific topic to study in this session"\n'
                    '    }\n'
                    '  ]\n'
                    "}\n\n"
                    "Return ONLY a valid JSON object. Do not include markdown code block syntax (like ```json)."
                )
                
                prompt = (
                    f"Design study schedule for:\n"
                    f"Exam Name: {exam_name or 'Upcoming Exam'}\n"
                    f"Exam Date: {exam_date or 'TBD'}\n"
                    f"Syllabus: {syllabus_context}\n"
                    f"Completed: {json.dumps(topics_completed)}\n"
                    f"Start Date: {start_date_str}\n\n"
                    f"User's Busy Calendar Events (DO NOT CLASH WITH THESE):\n"
                    f"{existing_events_str}\n\n"
                    "Place study sessions of 1.5 to 3.0 hours length per day, avoiding the busy slots listed above. "
                    "Try to schedule one session per day on the days leading up to the exam (excluding the exam day itself)."
                )

                # Query LLM to design the schedule
                param_text = await self.llm.query_llm(prompt, system_prompt=system_prompt, plain_text=False)
                
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
                    response_json = json.loads(param_text)
                    sessions_list = response_json.get("schedule", [])
                except Exception:
                    sessions_list = []

                if not sessions_list:
                    # Default backup scheduling if parsing fails
                    current_d = start_date_obj
                    days_scheduled = 0
                    while days_scheduled < 5 and (not exam_end_date or current_d <= exam_end_date):
                        sessions_list.append({
                            "date": current_d.isoformat(),
                            "start_time": "14:00",
                            "end_time": "16:00",
                            "topic": exam_name or "Study Session"
                        })
                        current_d += timedelta(days=1)
                        days_scheduled += 1

                # Convert raw_busy_intervals to a list of datetime tuples for simple clash checks
                local_busy_ranges = []
                for item in raw_busy_intervals:
                    s_dt = item["start"]
                    e_dt = item["end"]
                    if s_dt.tzinfo is None:
                        s_dt = s_dt.replace(tzinfo=ZoneInfo(tz_str))
                    else:
                        s_dt = s_dt.astimezone(ZoneInfo(tz_str))
                    if e_dt.tzinfo is None:
                        e_dt = e_dt.replace(tzinfo=ZoneInfo(tz_str))
                    else:
                        e_dt = e_dt.astimezone(ZoneInfo(tz_str))
                    local_busy_ranges.append((s_dt, e_dt))

                slots = []
                topics_per_slot = []
                
                # Check for overlap helper
                def has_clash(test_start, test_end):
                    for b_start, b_end in local_busy_ranges:
                        if test_start < b_end and test_end > b_start:
                            return True
                    return False

                # Helper to find free slot on a given date of a given duration
                def find_free_slot_on_day(target_date: date, duration: timedelta) -> Optional[Tuple[datetime, datetime]]:
                    start_boundary = datetime.combine(target_date, time(9, 0)).replace(tzinfo=ZoneInfo(tz_str))
                    end_boundary = datetime.combine(target_date, time(21, 0)).replace(tzinfo=ZoneInfo(tz_str))
                    
                    day_busy = []
                    for b_start, b_end in local_busy_ranges:
                        if b_start < end_boundary and b_end > start_boundary:
                            day_busy.append((max(b_start, start_boundary), min(b_end, end_boundary)))
                    day_busy.sort(key=lambda x: x[0])
                    
                    candidate = start_boundary
                    for b_start, b_end in day_busy:
                        if b_start - candidate >= duration:
                            return candidate, candidate + duration
                        candidate = max(candidate, b_end)
                    if end_boundary - candidate >= duration:
                        return candidate, candidate + duration
                    return None

                for session in sessions_list:
                    try:
                        s_date = date.fromisoformat(session["date"])
                        s_time = time.fromisoformat(session["start_time"])
                        e_time = time.fromisoformat(session["end_time"])
                        s_topic = session.get("topic") or exam_name or "Study Session"
                        
                        s_dt = datetime.combine(s_date, s_time).replace(tzinfo=ZoneInfo(tz_str))
                        e_dt = datetime.combine(s_date, e_time).replace(tzinfo=ZoneInfo(tz_str))
                        duration = e_dt - s_dt
                        if duration <= timedelta(0):
                            duration = timedelta(hours=2)
                            e_dt = s_dt + duration
                    except Exception:
                        continue
                        
                    # Check for clash
                    if has_clash(s_dt, e_dt):
                        adjusted = find_free_slot_on_day(s_date, duration)
                        if adjusted:
                            s_dt, e_dt = adjusted
                        else:
                            adjusted_found = False
                            for day_offset in range(1, 4):
                                adjusted = find_free_slot_on_day(s_date + timedelta(days=day_offset), duration)
                                if adjusted:
                                    s_dt, e_dt = adjusted
                                    adjusted_found = True
                                    break
                            if not adjusted_found:
                                continue
                                
                    slots.append((s_dt, e_dt))
                    topics_per_slot.append(s_topic)
                    local_busy_ranges.append((s_dt, e_dt))

                if slots:
                    created_events = []
                    for (s_dt, e_dt), topic in zip(slots, topics_per_slot):
                        events = insert_study_sessions(service, topic, [(s_dt, e_dt)], tz_str=tz_str)
                        if events:
                            created_events.extend(events)
                            
                    schedule_items = []
                    milestones = []
                    for i, ((s_dt, e_dt), topic) in enumerate(zip(slots, topics_per_slot), 1):
                        duration = e_dt - s_dt
                        duration_hours = duration.total_seconds() / 3600.0
                        schedule_items.append({
                            "day": i,
                            "date": s_dt.strftime("%Y-%m-%d"),
                            "topics": [topic],
                            "duration_hours": int(duration_hours) if duration_hours % 1 == 0 else round(duration_hours, 1),
                            "study_load": "high" if i == 1 else "medium" if i < len(slots) else "light",
                            "resources": []
                        })
                        if i == len(slots):
                            milestones.append({
                                "day": i,
                                "milestone": f"Finish {topic} revision"
                            })

                    slots_str = "\n".join([
                        f"- Session {i} ({s_dt.strftime('%A, %b %d')}): {s_dt.strftime('%I:%M %p')} - {e_dt.strftime('%I:%M %p')} -> Topic: {topic}"
                        for i, ((s_dt, e_dt), topic) in enumerate(zip(slots, topics_per_slot), 1)
                    ])
                    
                    study_prompt = (
                        f"I have successfully scheduled {len(slots)} study sessions in the user's Google Calendar:\n"
                        f"{slots_str}\n\n"
                        f"Generate a short study plan dividing the syllabus into these exact slots only:\n"
                        f"Exam: {exam_name or 'Upcoming Exam'} (Date: {exam_date or 'TBD'})\n"
                        f"Syllabus Context: {syllabus_context}\n"
                        f"Already completed: {json.dumps(topics_completed)}\n\n"
                        "Keep it concise. No markdown. No emojis. No special characters."
                    )
                    
                    system_prompt = (
                        "You are a professional Academic Planner. Guide the user through their study schedule, "
                        "mentioning that these slots have been booked in their Google Calendar. Keep the answer short."
                    )
                    
                    response_text = await self.llm.query_llm(study_prompt, system_prompt=system_prompt)
                    
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
        fallback_start = parse_iso_date_or_none(start_date) or date.today()
        fallback_exam = parse_iso_date_or_none(exam_date)
        if fallback_exam and fallback_start > fallback_exam:
            fallback_start = date.today()
            if fallback_start > fallback_exam:
                fallback_start = fallback_exam
        plan_days = ((fallback_exam - fallback_start).days + 1) if fallback_exam else 3
        plan_days = max(1, min(plan_days, 7))

        system_prompt = (
            "You are a professional Academic Planner. You must follow these safety guardrails strictly:\n"
            "- Only answer educational, academic, or study-related planning queries.\n"
            "- Do not process any inappropriate, sexual, adult, adulterous, violent, or unsafe content.\n"
            "Return a short plain text plan only. No markdown, emojis, bullets, tables, or special characters.\n"
            "Use only the requested date range. Do not create a week plan unless the range is seven days."
        )

        prompt = (
            f"Generate a daily study plan for the exam '{exam_name or 'Upcoming Exam'}' on {exam_date or 'TBD'}.\n"
            f"Start date: {fallback_start.isoformat()}.\n"
            f"Number of plan days: {plan_days}.\n"
            f"Syllabus Context: {syllabus_context}\n"
            f"Completed Topics: {json.dumps(topics_completed)}\n"
            "Each day should be one short line."
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
