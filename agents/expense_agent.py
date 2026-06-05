import json
from groq import Groq
from config import Config

class ExpenseAgent:
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
    async def process_receipt(self, image_base64: str, prompt_text: str = None) -> dict:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]

        prompt = (
            f"Analyze this receipt image. It may contain handwritten text or notes. Perform OCR, read the items and totals, and extract the details.\n"
            f"Provide a clear human-readable summary of the expense, including total amount, merchant, date, and category.\n"
            f"User additional instruction: {prompt_text or 'None'}"
        )

        response = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
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
                }
            ]
        )

        response_text = response.choices[0].message.content
        print(f"[ExpenseAgent] LLM Response: {response_text}")
        return {"response": response_text, "amount": 0.0, "category": "Others", "merchant": "Unknown", "date": "", "confidence": 0.0}
