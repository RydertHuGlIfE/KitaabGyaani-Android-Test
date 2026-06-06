from groq import Groq
from config import Config
import re

PLAIN_RESPONSE_INSTRUCTION = (
    "For user-facing answers, be short and concise. Use plain ASCII text only. "
    "Do not use emojis, markdown, bullets, tables, decorative symbols, or special characters. "
    "Prefer 3 to 6 short lines unless the user explicitly asks for more detail."
)


def sanitize_user_response(text: str, max_chars: int = 1200) -> str:
    if not text:
        return ""

    replacements = {
        "\u2022": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), text)
    text = re.sub(r"[*_`#>~]", "", text)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", text)
    text = re.sub(r"(?:(?<=\s)|^)\?+(?=\s|$)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip(" -") for line in text.splitlines())
    text = text.strip()

    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip()
    return text

class LLMService:
    def __init__(self):
        self.groq_client = Groq(api_key=Config.GROQ_API_KEY)

    async def query_llm(self, prompt: str, system_prompt: str = None, use_groq: bool = True, model: str = None, plain_text: bool = True) -> str:
        messages = []
        full_system_prompt = system_prompt or ""
        if plain_text:
            full_system_prompt = f"{full_system_prompt}\n\n{PLAIN_RESPONSE_INSTRUCTION}".strip()
        if full_system_prompt:
            messages.append({"role": "system", "content": full_system_prompt})
        messages.append({"role": "user", "content": prompt})

        selected_model = model or "llama-3.3-70b-versatile"
        response = self.groq_client.chat.completions.create(
            model=selected_model,
            messages=messages
        )
        content = response.choices[0].message.content
        return sanitize_user_response(content) if plain_text else content

    async def query_vision_llm(self, image_base64: str, prompt: str, system_prompt: str = None, plain_text: bool = True) -> str:
        messages = []
        full_system_prompt = system_prompt or ""
        if plain_text:
            full_system_prompt = f"{full_system_prompt}\n\n{PLAIN_RESPONSE_INSTRUCTION}".strip()
        if full_system_prompt:
            messages.append({"role": "system", "content": full_system_prompt})
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
        content = response.choices[0].message.content
        return sanitize_user_response(content) if plain_text else content

