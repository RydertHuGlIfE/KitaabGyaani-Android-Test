import time
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from config import Config
from services.llm_service import LLMService
from services.ocr_service import OCRService
from services.pdf_service import PDFService
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
pdf_service = PDFService()

study_agent = StudyAgent(llm_service, ocr_service, pdf_service)
planner_agent = PlannerAgent(llm_service)
expense_agent = ExpenseAgent()
content_agent = ContentAgent(llm_service)

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KitaabGyaani Testing Window</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #f3f4f6; }
    </style>
</head>
<body class="p-6">
    <div class="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
        <h1 class="text-2xl font-bold text-indigo-400 mb-6">KitaabGyaani Tester</h1>
        
        <div class="flex space-x-2 border-b border-slate-800 pb-3 mb-6 overflow-x-auto">
            <button onclick="switchTab('study')" id="btn-study" class="tab-btn px-4 py-2 rounded bg-indigo-600 text-white font-medium">Study Agent</button>
            <button onclick="switchTab('planner')" id="btn-planner" class="tab-btn px-4 py-2 rounded bg-slate-800 text-slate-300 font-medium">Planner</button>
            <button onclick="switchTab('expense')" id="btn-expense" class="tab-btn px-4 py-2 rounded bg-slate-800 text-slate-300 font-medium">Expense</button>
            <button onclick="switchTab('content')" id="btn-content" class="tab-btn px-4 py-2 rounded bg-slate-800 text-slate-300 font-medium">Content</button>
            <button onclick="switchTab('websocket')" id="btn-websocket" class="tab-btn px-4 py-2 rounded bg-slate-800 text-slate-300 font-medium">WebSocket</button>
        </div>

        <div id="tab-study" class="tab-content">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-1">Upload File (PDF or Image) or write text below</label>
                    <input type="file" id="study-file" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1">Raw Text Content</label>
                    <textarea id="study-text" rows="5" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100" placeholder="Paste study text here..."></textarea>
                </div>
                <button onclick="runStudy()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded w-full">Process Study Material</button>
            </div>
        </div>

        <div id="tab-planner" class="tab-content hidden">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-1">Exam Name</label>
                    <input type="text" id="plan-name" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100" value="Database Management Systems">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1">Exam Date</label>
                    <input type="date" id="plan-date" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1">Syllabus Topics (comma-separated)</label>
                    <input type="text" id="plan-syllabus" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100" value="Introduction, ER Model, Relational Algebra, Normalization, SQL, Indexing">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1">Completed Topics (comma-separated)</label>
                    <input type="text" id="plan-completed" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100" value="Introduction, ER Model">
                </div>
                <button onclick="runPlanner()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded w-full">Generate Schedule</button>
            </div>
        </div>

        <div id="tab-expense" class="tab-content hidden">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-1">Upload Receipt Image</label>
                    <input type="file" id="expense-file" accept="image/*" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm">
                </div>
                <button onclick="runExpense()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded w-full">Extract & Categorize Expense</button>
            </div>
        </div>

        <div id="tab-content" class="tab-content hidden">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-1">Task</label>
                    <input type="text" id="content-task" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100" value="Write internship application email">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1">Context</label>
                    <textarea id="content-context" rows="4" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm text-slate-100" placeholder="Targeting Google, software engineer role, specialized in Python and machine learning."></textarea>
                </div>
                <button onclick="runContent()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded w-full">Draft Content</button>
            </div>
        </div>

        <div id="tab-websocket" class="tab-content hidden">
            <div class="space-y-4">
                <div class="flex items-center space-x-2">
                    <span class="text-sm font-medium">WS Status:</span>
                    <span id="ws-status" class="px-2 py-1 text-xs rounded bg-red-900 text-red-100 font-bold">Disconnected</span>
                    <button onclick="connectWS()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs px-2 py-1 rounded">Connect</button>
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1">Custom JSON Payload</label>
                    <textarea id="ws-payload" rows="6" class="w-full bg-slate-800 border border-slate-700 rounded p-2 text-sm font-mono text-slate-100">{
  "id": "req_test",
  "agent": "study",
  "action": "generate_summary",
  "payload": {
    "content": "Normalized schemas avoid redundancy and ensure database consistency."
  }
}</textarea>
                </div>
                <button onclick="sendWS()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded w-full">Send JSON via WebSocket</button>
                <div>
                    <label class="block text-sm font-medium mb-1">WebSocket Logs</label>
                    <div id="ws-logs" class="bg-black border border-slate-800 p-3 rounded h-60 overflow-y-auto font-mono text-xs text-emerald-400 space-y-2"></div>
                </div>
            </div>
        </div>

        <div class="mt-8 border-t border-slate-800 pt-6">
            <h2 class="text-lg font-semibold text-indigo-400 mb-2">Output Result</h2>
            <pre id="output-result" class="bg-black border border-slate-800 p-4 rounded text-emerald-400 font-mono text-xs overflow-x-auto max-h-96">No requests made yet.</pre>
        </div>
    </div>

    <script>
        let wsClient = null;

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('bg-indigo-600', 'text-white');
                btn.classList.add('bg-slate-800', 'text-slate-300');
            });

            document.getElementById('tab-' + tabId).classList.remove('hidden');
            document.getElementById('btn-' + tabId).classList.remove('bg-slate-800', 'text-slate-300');
            document.getElementById('btn-' + tabId).classList.add('bg-indigo-600', 'text-white');
        }

        async function fileToBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = () => resolve(reader.result);
                reader.onerror = error => reject(error);
            });
        }

        function displayResult(data) {
            document.getElementById('output-result').textContent = JSON.stringify(data, null, 2);
        }

        async function runStudy() {
            const fileInput = document.getElementById('study-file');
            const textInput = document.getElementById('study-text').value;
            let content = textInput;
            let isImage = false;

            if (fileInput.files.length > 0) {
                const file = fileInput.files[0];
                const base64 = await fileToBase64(file);
                content = base64;
                isImage = file.type.startsWith('image/');
            }

            if (!content) return alert("Please upload a file or write text.");

            displayResult("Processing...");
            try {
                const response = await fetch('/api/agents/study/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content, is_image: isImage })
                });
                const data = await response.json();
                displayResult(data);
            } catch (err) {
                displayResult({ error: err.message });
            }
        }

        async function runPlanner() {
            const name = document.getElementById('plan-name').value;
            const date = document.getElementById('plan-date').value;
            const syllabus = document.getElementById('plan-syllabus').value.split(',').map(s => s.trim());
            const completed = document.getElementById('plan-completed').value.split(',').map(c => c.trim());

            if (!name || !date) return alert("Exam Name and Date are required.");

            displayResult("Generating Schedule...");
            try {
                const response = await fetch('/api/agents/planner/schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        exam_name: name,
                        exam_date: date,
                        topics_completed: completed,
                        syllabus: syllabus
                    })
                });
                const data = await response.json();
                displayResult(data);
            } catch (err) {
                displayResult({ error: err.message });
            }
        }

        async function runExpense() {
            const fileInput = document.getElementById('expense-file');
            if (fileInput.files.length === 0) return alert("Please select a receipt image.");

            displayResult("Processing Receipt...");
            try {
                const base64 = await fileToBase64(fileInput.files[0]);
                const response = await fetch('/api/agents/expense/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_base64: base64 })
                });
                const data = await response.json();
                displayResult(data);
            } catch (err) {
                displayResult({ error: err.message });
            }
        }

        async function runContent() {
            const task = document.getElementById('content-task').value;
            const context = document.getElementById('content-context').value;

            if (!task) return alert("Task is required.");

            displayResult("Drafting content...");
            try {
                const response = await fetch('/api/agents/content/draft', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ task: task, context: context })
                });
                const data = await response.json();
                displayResult(data);
            } catch (err) {
                displayResult({ error: err.message });
            }
        }

        function logWS(msg, type = "info") {
            const logs = document.getElementById('ws-logs');
            const div = document.createElement('div');
            div.className = type === "send" ? "text-blue-400" : type === "receive" ? "text-emerald-400" : "text-yellow-400";
            div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logs.appendChild(div);
            logs.scrollTop = logs.scrollHeight;
        }

        function connectWS() {
            if (wsClient) wsClient.close();
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            logWS("Connecting to " + wsUrl);

            wsClient = new WebSocket(wsUrl);

            wsClient.onopen = () => {
                document.getElementById('ws-status').className = "px-2 py-1 text-xs rounded bg-emerald-900 text-emerald-100 font-bold";
                document.getElementById('ws-status').textContent = "Connected";
                logWS("Connected successfully!");
            };

            wsClient.onclose = () => {
                document.getElementById('ws-status').className = "px-2 py-1 text-xs rounded bg-red-900 text-red-100 font-bold";
                document.getElementById('ws-status').textContent = "Disconnected";
                logWS("Disconnected.");
            };

            wsClient.onmessage = (event) => {
                logWS("Received response: " + event.data.substring(0, 150) + "...", "receive");
                try {
                    displayResult(JSON.parse(event.data));
                } catch(e) {
                    displayResult(event.data);
                }
            };

            wsClient.onerror = (err) => {
                logWS("Error: " + err.message, "error");
            };
        }

        function sendWS() {
            if (!wsClient || wsClient.readyState !== WebSocket.OPEN) {
                return alert("WebSocket is not connected. Click 'Connect' first.");
            }
            const payload = document.getElementById('ws-payload').value;
            wsClient.send(payload);
            logWS("Sent payload", "send");
        }

        document.getElementById('plan-date').valueAsDate = new Date(Date.now() + 10 * 24 * 60 * 60 * 1000);
        connectWS();
    </script>
</body>
</html>"""



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
