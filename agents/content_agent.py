import json
from services.llm_service import LLMService

class ContentAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def draft_content(self, task: str, context: str) -> dict:
        system_prompt = "You are a Professional Content Writer. Respond briefly in plain ASCII text. No markdown, emojis, bullets, or special characters."
        prompt = (
            f"Draft content for the following task: '{task}'.\n"
            f"Context: {context}\n\n"
            "Return a concise draft and at most two short suggestions."
        )
        
        response_text = await self.llm.query_llm(prompt, system_prompt=system_prompt, use_groq=True)
        return {"response": response_text, "draft_text": response_text, "suggestions": [], "tone": "formal"}
