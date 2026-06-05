import json
from services.llm_service import LLMService

class ContentAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def draft_content(self, task: str, context: str) -> dict:
        system_prompt = "You are a Professional Content Writer. Output your response as a valid JSON object only."
        prompt = (
            f"Draft content for the following task: '{task}'.\n"
            f"Context: {context}\n\n"
            "Format the output strictly as a JSON object with this structure:\n"
            "{\n"
            '  "draft_text": "complete draft text here with newlines",\n'
            '  "suggestions": ["suggestion1", "suggestion2"],\n'
            '  "tone": "formal"\n'
            "}"
        )
        
        response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt, use_groq=True)
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
            return {"draft_text": response_text, "suggestions": [], "tone": "formal"}
