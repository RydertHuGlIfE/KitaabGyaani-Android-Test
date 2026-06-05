from groq import Groq
from config import Config

class OCRService:
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)

    def extract_text(self, image_base64: str) -> str:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
            
        response = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Perform precise OCR on this image. Return only the extracted text."},
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
        return response.choices[0].message.content
