import os
import sys
import asyncio

# Add root directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService
from agents.planner_agent import PlannerAgent

async def main():
    print("Testing PlannerAgent.generate_schedule...")
    llm = LLMService()
    ocr = OCRService()
    pdf = PDFService()
    agent = PlannerAgent(llm, ocr, pdf)
    
    try:
        res = await agent.generate_schedule(
            exam_name="Database Management Systems",
            exam_date="2026-06-15",
            topics_completed=[],
            syllabus=["ER Model", "Relational Algebra", "Normalization"],
            start_date="2026-06-08"
        )
        print("SUCCESS! Result:")
        import json
        print(json.dumps(res, indent=2))
    except Exception as e:
        print("EXCEPTION in generate_schedule:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
