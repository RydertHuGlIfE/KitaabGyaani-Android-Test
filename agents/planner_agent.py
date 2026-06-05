import json
from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService

class PlannerAgent:
    def __init__(self, llm_service: LLMService, ocr_service: OCRService, pdf_service: PDFService):
        self.llm = llm_service
        self.ocr = ocr_service
        self.pdf = pdf_service

    async def generate_schedule(
        self, exam_name: str, exam_date: str, topics_completed: list, syllabus: list,
        content: str = None, is_image: bool = False
    ) -> dict:
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

        system_prompt = (
            "You are a professional Academic Planner. Output your response as a valid JSON object only.\n"
            "You must follow these safety guardrails strictly:\n"
            "- Only answer educational, academic, or study-related planning queries.\n"
            "- Do not process any inappropriate, sexual, adult, adulterous, violent, or unsafe content."
        )

        syllabus_context = json.dumps(syllabus)
        if extracted_syllabus:
            syllabus_context += f"\nAdditional Extracted Syllabus/Schedule details from document:\n{extracted_syllabus}"

        prompt = (
            f"Generate a daily study plan for the exam '{exam_name or 'Upcoming Exam'}' on {exam_date or 'TBD'}.\n"
            f"Syllabus Context: {syllabus_context}\n"
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
            return {"exam_name": exam_name or "Upcoming Exam", "exam_date": exam_date or "TBD", "schedule": [], "milestones": []}
