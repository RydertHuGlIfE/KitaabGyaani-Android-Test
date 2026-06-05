from groq import Groq
from config import Config

class LLMService:
    def __init__(self):
        self.groq_client = Groq(api_key=Config.GROQ_API_KEY)

    async def query_llm(self, prompt: str, system_prompt: str = None, use_groq: bool = True, model: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        selected_model = model or "llama-3.3-70b-versatile"
        response = self.groq_client.chat.completions.create(
            model=selected_model,
            messages=messages
        )
        return response.choices[0].message.content

