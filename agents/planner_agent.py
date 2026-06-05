import json
from services.llm_service import LLMService

class PlannerAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def generate_schedule(self, exam_name: str, exam_date: str, topics_completed: list, syllabus: list) -> dict:
        system_prompt = "You are an Academic Planner. Output your response as a valid JSON object only."
        prompt = (
            f"Generate a daily study plan for the exam '{exam_name}' on {exam_date}.\n"
            f"Syllabus: {json.dumps(syllabus)}\n"
            f"Completed Topics: {json.dumps(topics_completed)}\n\n"
            "Format the output strictly as a JSON object with this structure:\n"
            "{\n"
            '  "exam_name": "name",\n'
            '  "exam_date": "date",\n'
            '  "schedule": [\n'
            "    {\n"
            '      "day": 1,\n'
            '      "date": "YYYY-MM-DD",\n'
            '      "topics": ["topic1", "topic2"],\n'
            '      "duration_hours": 2,\n'
            '      "study_load": "medium",\n'
            '      "resources": ["resource1"]\n'
            "    }\n"
            "  ],\n"
            '  "milestones": [{"day": 3, "milestone": "milestone description"}]\n'
            "}"
        )
        
        response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != -1:
                    return json.loads(response_text[start:end])
            except Exception:
                pass
            return {"exam_name": exam_name, "exam_date": exam_date, "schedule": [], "milestones": []}
