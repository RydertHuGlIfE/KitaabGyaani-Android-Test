import asyncio
from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService
from agents.planner_agent import PlannerAgent

async def test():
    llm = LLMService()
    ocr = OCRService()
    pdf = PDFService()
    planner = PlannerAgent(llm, ocr, pdf)
    
    print("Running planner agent...")
    try:
        res = await planner.generate_schedule(
            exam_name="Math Exam",
            exam_date="2026-06-25",
            topics_completed=[],
            syllabus=["Algebra", "Calculus"]
        )
        print("Result:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
