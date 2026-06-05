import asyncio
import sys
import os

# Add root folder to python path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService
from agents.study_agent import StudyAgent

async def test_endpoint():
    llm = LLMService()
    ocr = OCRService()
    pdf = PDFService()
    agent = StudyAgent(llm, ocr, pdf)
    
    # 1x1 transparent PNG base64
    mock_base64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    
    try:
        print("Invoking StudyAgent.process_material with mock image...")
        result = await agent.process_material(
            content=mock_base64_image,
            is_image=True,
            prompt_text="Hello, analyze this image"
        )
        print("Agent response:", result)
    except Exception as e:
        import traceback
        print("\n--- ERROR OCCURRED ---")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_endpoint())
