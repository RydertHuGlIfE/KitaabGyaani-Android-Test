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

    async def query_vision_llm(self, image_base64: str, prompt: str, system_prompt: str = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        })

        response = self.groq_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=messages
        )
        return response.choices[0].message.content

