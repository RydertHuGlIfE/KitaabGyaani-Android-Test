import json
from groq import Groq
from config import Config

class ExpenseAgent:
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)

    async def process_receipt(self, image_base64: str) -> dict:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]

        prompt = (
            "Analyze this receipt image. Perform OCR and extract the details as a valid JSON object. "
            "Categorize the transaction into one of these: Food, Books, Transport, Utilities, Entertainment, Others. "
            "Format the output strictly as a JSON object with this structure:\n"
            "{\n"
            '  "amount": 0.00,\n'
            '  "category": "CategoryName",\n'
            '  "merchant": "MerchantName",\n'
            '  "date": "YYYY-MM-DD",\n'
            '  "confidence": 0.95\n'
            "}"
        )

        response = self.client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
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
            return {"amount": 0.0, "category": "Others", "merchant": "Unknown", "date": "", "confidence": 0.0}
