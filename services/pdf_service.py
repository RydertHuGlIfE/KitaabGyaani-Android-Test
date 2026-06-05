import base64
from io import BytesIO
import PyPDF2

class PDFService:
    def extract_text(self, pdf_base64: str) -> str:
        if "," in pdf_base64:
            pdf_base64 = pdf_base64.split(",")[1]
            
        pdf_bytes = base64.b64decode(pdf_base64)
        pdf_file_obj = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file_obj)
        pdf_text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                pdf_text += page_text + "\n"
        return pdf_text
