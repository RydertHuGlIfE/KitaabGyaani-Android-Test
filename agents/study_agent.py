import json
from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService

class StudyAgent:
    def __init__(self, llm_service: LLMService, ocr_service: OCRService, pdf_service: PDFService):
        self.llm = llm_service
        self.ocr = ocr_service
        self.pdf = pdf_service

    async def process_material(self, content: str, is_image: bool = False, prompt_text: str = None, chat_history: list = None) -> dict:
        text = content
        
        cleaned_content = content
        if "," in content:
            cleaned_content = content.split(",")[1]
            
        is_pdf = cleaned_content.startswith("JVBERi")
        
        # Convert conversational text to prompt_text if it is short and not a file
        if not prompt_text and not is_pdf and not is_image and len(cleaned_content) < 500:
            prompt_text = content

        # Format chat history context if available
        history_str = ""
        if chat_history:
            for msg in chat_history[-10:]:
                role = "User" if msg.get("sender") == "user" else "AI"
                msg_text = msg.get("text", "")
                if msg.get("is_image"):
                    msg_text = f"[Attached Image] {msg_text}"
                history_str += f"{role}: {msg_text}\n"
        
        system_prompt = (
            "You are a helpful, professional academic Study Assistant. You must follow these safety guardrails strictly:\n"
            "- Only answer educational, academic, or study-related queries.\n"
            "- Do not process, generate, or discuss any inappropriate, sexual, adult, adulterous, violent, or unsafe content.\n"
            "- If a query is off-topic or inappropriate, politely decline by stating that you are an academic assistant.\n"
            "- Give detailed, concise, and helpful information about what is asked.\n"
            "If conversation history is provided, use it to maintain context and refer back to previous discussed topics if relevant."
        )

        response_text = ""
        if prompt_text:
            # Custom user query flow with guardrails
            if is_pdf:
                text = self.pdf.extract_text(content)
                prompt = f"Using the following study notes/document and conversation history, answer this instruction: {prompt_text}\n\nConversation History:\n{history_str}\n\nDocument Context:\n{text}"
                response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt)
            elif is_image:
                prompt = f"Conversation History:\n{history_str}\n\nInstruction: {prompt_text}"
                response_text = await self.llm.query_vision_llm(cleaned_content, prompt, system_prompt=system_prompt)
            else:
                prompt = f"Using the following context and conversation history, answer this instruction: {prompt_text}\n\nConversation History:\n{history_str}\n\nContext:\n{text}"
                response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt)
        else:
            # Predefined structured study kit flow
            system_prompt_json = (
                "You are a Study Assistant. Output your response as a valid JSON object only.\n"
                "You must follow these safety guardrails strictly:\n"
                "- Only answer educational, academic, or study-related queries.\n"
                "- Do not process any inappropriate, sexual, adult, adulterous, violent, or unsafe content.\n"
                "- If a query is off-topic or inappropriate, politely decline by stating that you are an academic assistant."
            )
            
            if is_pdf:
                text = self.pdf.extract_text(content)
                prompt = (
                    f"Generate a study kit from the following text:\n\n{text}\n\n"
                    "Format the output strictly as a JSON object with this structure:\n"
                    "{\n"
                    '  "summary": "detailed summary here",\n'
                    '  "flashcards": [{"q": "question", "a": "answer"}],\n'
                    '  "mcqs": [{"q": "question", "options": ["option1", "option2", "option3", "option4"], "answer": "correct_option"}]\n'
                    "}"
                )
                response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt_json)
            elif is_image:
                prompt = (
                    "Analyze this study material image and generate a study kit.\n"
                    "Format the output strictly as a JSON object with this structure:\n"
                    "{\n"
                    '  "summary": "detailed summary here",\n'
                    '  "flashcards": [{"q": "question", "a": "answer"}],\n'
                    '  "mcqs": [{"q": "question", "options": ["option1", "option2", "option3", "option4"], "answer": "correct_option"}]\n'
                    "}"
                )
                response_text = await self.llm.query_vision_llm(cleaned_content, prompt, system_prompt=system_prompt_json)
            else:
                prompt = (
                    f"Generate a study kit from the following text:\n\n{text}\n\n"
                    "Format the output strictly as a JSON object with this structure:\n"
                    "{\n"
                    '  "summary": "detailed summary here",\n'
                    '  "flashcards": [{"q": "question", "a": "answer"}],\n'
                    '  "mcqs": [{"q": "question", "options": ["option1", "option2", "option3", "option4"], "answer": "correct_option"}]\n'
                    "}"
                )
                response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt_json)
            
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


