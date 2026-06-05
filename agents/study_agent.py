import json
from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService

class StudyAgent:
    def __init__(self, llm_service: LLMService, ocr_service: OCRService, pdf_service: PDFService):
        self.llm = llm_service
        self.ocr = ocr_service
        self.pdf = pdf_service

    async def process_material(self, content: str, is_image: bool = False) -> dict:
        text = content
        
        cleaned_content = content
        if "," in content:
            cleaned_content = content.split(",")[1]
            
        is_pdf = cleaned_content.startswith("JVBERi")
        
        if is_pdf:
            text = self.pdf.extract_text(content)
        elif is_image:
            text = self.ocr.extract_text(content)
            
        system_prompt = "You are a Study Assistant. Output your response as a valid JSON object only."
        prompt = (
            f"Generate a study kit from the following text:\n\n{text}\n\n"
            "Format the output strictly as a JSON object with this structure:\n"
            "{\n"
            '  "summary": "detailed summary here",\n'
            '  "flashcards": [{"q": "question", "a": "answer"}],\n'
            '  "mcqs": [{"q": "question", "options": ["option1", "option2", "option3", "option4"], "answer": "correct_option"}]\n'
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
            return {"summary": response_text, "flashcards": [], "mcqs": []}

