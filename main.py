import time
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from config import Config
from services.llm_service import LLMService
from services.ocr_service import OCRService
from agents.study_agent import StudyAgent
from agents.planner_agent import PlannerAgent
from agents.expense_agent import ExpenseAgent
from agents.content_agent import ContentAgent

app = FastAPI(title="KitaabGyaani Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_service = LLMService()
ocr_service = OCRService()

study_agent = StudyAgent(llm_service, ocr_service)
planner_agent = PlannerAgent(llm_service)
expense_agent = ExpenseAgent()
content_agent = ContentAgent(llm_service)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

class StudyRequest(BaseModel):
    content: str
    is_image: bool = False

class PlannerRequest(BaseModel):
    exam_name: str
    exam_date: str
    topics_completed: List[str]
    syllabus: List[str]

class ExpenseRequest(BaseModel):
    image_base64: str

class ContentRequest(BaseModel):
    task: str
    context: str

@app.post("/api/agents/study/process")
async def process_study(req: StudyRequest):
    try:
        return await study_agent.process_material(req.content, req.is_image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/planner/schedule")
async def process_planner(req: PlannerRequest):
    try:
        return await planner_agent.generate_schedule(
            req.exam_name, req.exam_date, req.topics_completed, req.syllabus
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/expense/process")
async def process_expense(req: ExpenseRequest):
    try:
        return await expense_agent.process_receipt(req.image_base64)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/content/draft")
async def process_content(req: ContentRequest):
    try:
        return await content_agent.draft_content(req.task, req.context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            
            req_id = request.get("id", "")
            agent = request.get("agent", "")
            action = request.get("action", "")
            payload = request.get("payload", {})
            
            start_time = time.time()
            result = {}
            status = "success"
            
            try:
                if agent == "study":
                    is_image = payload.get("is_image", False) or payload.get("file_base64") is not None
                    content = payload.get("file_base64") or payload.get("content", "")
                    result = await study_agent.process_material(content, is_image)
                elif agent == "planner":
                    result = await planner_agent.generate_schedule(
                        payload.get("exam_name", ""),
                        payload.get("exam_date", ""),
                        payload.get("topics_completed", []),
                        payload.get("syllabus", [])
                    )
                elif agent == "expense":
                    result = await expense_agent.process_receipt(payload.get("image_base64", ""))
                elif agent == "content":
                    result = await content_agent.draft_content(
                        payload.get("task", ""),
                        payload.get("context", "")
                    )
                else:
                    status = "error"
                    result = {"detail": f"Unknown agent: {agent}"}
            except Exception as e:
                status = "error"
                result = {"detail": str(e)}
                
            response = {
                "request_id": req_id,
                "status": status,
                "agent": agent,
                "data": result,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "server_timestamp": int(time.time())
            }
            await manager.send_message(response, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)
