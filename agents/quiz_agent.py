import json
from services.llm_service import LLMService
from services.pdf_service import PDFService

class QuizAgent:
    def __init__(self, llm_service: LLMService, pdf_service: PDFService):
        self.llm = llm_service
        self.pdf = pdf_service

    async def generate_quiz(self, content: str = None, is_image: bool = False, topic: str = None) -> list:
        extracted_text = ""
        
        # 1. Parse PDF/Image if attached
        if content:
            cleaned_content = content
            if "," in content:
                cleaned_content = content.split(",")[1]
            is_pdf = cleaned_content.startswith("JVBERi")
            if is_pdf:
                extracted_text = self.pdf.extract_text(content)
            elif is_image:
                vision_prompt = "Perform OCR on this image. Extract all text content and concepts for creating a study quiz. Output only the extracted details."
                extracted_text = await self.llm.query_vision_llm(cleaned_content, vision_prompt)
            else:
                extracted_text = content

        # 2. Setup prompt based on topic or context
        context_description = f"Topic: {topic}" if topic else "Uploaded Study Material"
        prompt = (
            f"You are an expert Quiz Master. Generate exactly 20 high-quality, relevant Multiple Choice Questions (MCQs) "
            f"based on this source: {context_description}.\n\n"
            f"Source text/content:\n{extracted_text if extracted_text else topic}\n\n"
            "Format your response STRICTLY as a valid JSON array of objects. Do not include markdown tags like ```json or any explanation. "
            "Use this exact JSON schema:\n"
            "[\n"
            "  {\n"
            "    \"question\": \"The question text?\",\n"
            "    \"options\": [\"Option 1\", \"Option 2\", \"Option 3\", \"Option 4\"],\n"
            "    \"correctIndex\": 0\n"
            "  }\n"
            "]"
        )

        system_prompt = (
            "You are a helpful Quiz Generation System. You must follow these safety guardrails strictly:\n"
            "- Only answer educational, academic, or study-related queries.\n"
            "- Do not process any inappropriate, sexual, adult, violent, or unsafe content.\n"
            "Output valid JSON only. Do not include introductory or concluding remarks."
        )

        response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt, plain_text=False)
        
        # Parse the JSON response
        try:
            # Clean possible markdown wrap
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
                
            return json.loads(cleaned)
        except Exception as e:
            print(f"[QuizAgent] JSON parsing error: {e}, Raw response: {response_text}")
            # Fallback mock quiz if parsing fails
            return [
                {
                    "question": f"Study Question about {topic or 'Material'}?",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correctIndex": 0
                }
            ]
