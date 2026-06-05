import time
import json
import os
import uuid
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
planner_agent = PlannerAgent(llm_service, ocr_service, pdf_service)
expense_agent = ExpenseAgent()
content_agent = ContentAgent(llm_service)

HISTORY_FILE = "chats_history.json"
chat_history_db = {
    "study": [],
    "planner": [],
    "expense": [],
    "content": []
}

def load_chat_history():
    global chat_history_db
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
                migrated = {}
                for agent in ["study", "planner", "expense", "content"]:
                    agent_data = data.get(agent, [])
                    # Check if legacy format (direct list of message dicts)
                    if agent_data and isinstance(agent_data, list) and isinstance(agent_data[0], dict) and "sender" in agent_data[0]:
                        migrated[agent] = [{
                            "id": "default_session",
                            "title": "Previous Chat",
                            "messages": agent_data
                        }]
                    elif agent_data and isinstance(agent_data, list) and all(isinstance(x, dict) and "messages" in x for x in agent_data):
                        migrated[agent] = agent_data
                    else:
                        migrated[agent] = []
                chat_history_db = migrated
    except Exception as e:
        print(f"Error loading chat history: {e}")

def save_chat_history():
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(chat_history_db, f, indent=2)
    except Exception as e:
        print(f"Error saving chat history: {e}")

load_chat_history()

def get_or_create_session(agent: str, session_id: Optional[str] = None, initial_title: str = "New Chat") -> tuple:
    sessions = chat_history_db.setdefault(agent, [])
    session = None
    if session_id:
        for s in sessions:
            if s.get("id") == session_id:
                session = s
                break
    
    if not session:
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "title": initial_title,
            "messages": []
        }
        sessions.append(session)
    return session, session_id

def update_session_title_and_append(agent: str, session_id: Optional[str], user_msg: dict, agent_msg: dict) -> str:
    session, actual_session_id = get_or_create_session(agent, session_id)
    
    # Generate cleaner title from user prompt if default
    if session["title"] == "New Chat" or session["title"] == "Previous Chat":
        text = user_msg.get("text", "")
        if text:
            title = text[:30].strip()
            if len(text) > 30:
                title += "..."
            session["title"] = title
        elif user_msg.get("image_base64"):
            session["title"] = "Attached Image"
        else:
            session["title"] = "Document Chat"
            
    session["messages"].append(user_msg)
    session["messages"].append(agent_msg)
    session["messages"] = session["messages"][-30:] # Keep active session length reasonable
    
    save_chat_history()
    return actual_session_id

def format_agent_response(agent: str, data: dict) -> str:
    try:
        if isinstance(data, str):
            return data
        if isinstance(data, dict) and "response" in data:
            return data["response"]
            
        if agent == "study":
            summary = data.get("summary", "")
            flashcards = data.get("flashcards") or []
            mcqs = data.get("mcqs") or []
            out = f"📚 SUMMARY:\n{summary}\n\n🏷️ FLASHCARDS:\n"
            for fc in flashcards:
                if isinstance(fc, dict):
                    out += f"• Q: {fc.get('q', '')}\n  A: {fc.get('a', '')}\n"
            out += "\n📝 MCQs:\n"
            for m in mcqs:
                if isinstance(m, dict):
                    opts = m.get("options") or []
                    options_str = ", ".join(opts) if isinstance(opts, list) else str(opts)
                    out += f"• {m.get('q', '')}\n  Options: {options_str}\n  Answer: {m.get('answer', '')}\n"
            return out
        elif agent == "planner":
            exam_name = data.get("exam_name", "")
            exam_date = data.get("exam_date", "")
            schedule = data.get("schedule") or []
            milestones = data.get("milestones") or []
            out = f"📅 STUDY SCHEDULE FOR: {exam_name} (Date: {exam_date})\n\n"
            for s in schedule:
                if isinstance(s, dict):
                    topics = s.get("topics") or []
                    topics_str = ", ".join(topics) if isinstance(topics, list) else str(topics)
                    resources = s.get("resources") or []
                    resources_str = ", ".join(resources) if isinstance(resources, list) else str(resources)
                    out += f"• Day {s.get('day', '')} ({s.get('date', '')}):\n  Topics: {topics_str}\n  Hours: {s.get('duration_hours', '')}h ({s.get('study_load', '')} load)\n  Resources: {resources_str}\n"
            if milestones:
                out += "\n🎯 MILESTONES:\n"
                for m in milestones:
                    if isinstance(m, dict):
                        out += f"• Day {m.get('day', '')}: {m.get('milestone', '')}\n"
            return out
        elif agent == "expense":
            amount = data.get("amount", 0.0)
            merchant = data.get("merchant", "Unknown")
            category = data.get("category", "Uncategorized")
            date = data.get("date", "TBD")
            confidence = data.get("confidence", 1.0)
            return f"💵 EXPENSE RECEIPT EXTRACTED:\n\n• Amount: ${amount}\n• Merchant: {merchant}\n• Category: {category}\n• Date: {date}\n• Confidence: {int(confidence * 100)}%"
        elif agent == "content":
            draft_text = data.get("draft_text", "")
            suggestions = data.get("suggestions", [])
            s_str = "\n".join([f"• {sg}" for sg in suggestions])
            return f"📝 DRAFTED TEXT:\n\n{draft_text}\n\n💡 Suggestions:\n{s_str}"
    except Exception as e:
        print(f"Formatting error: {e}")
    return str(data)


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
    prompt_text: Optional[str] = None
    session_id: Optional[str] = None

class PlannerRequest(BaseModel):
    exam_name: Optional[str] = ""
    exam_date: Optional[str] = ""
    topics_completed: Optional[List[str]] = []
    syllabus: Optional[List[str]] = []
    content: Optional[str] = None
    is_image: bool = False
    session_id: Optional[str] = None

class ExpenseRequest(BaseModel):
    image_base64: str
    prompt_text: Optional[str] = None
    session_id: Optional[str] = None

class ContentRequest(BaseModel):
    task: str
    context: str
    session_id: Optional[str] = None

@app.post("/api/chat/history")
async def get_chat_history():
    return chat_history_db

@app.post("/api/chat/clear")
async def clear_chat_history():
    global chat_history_db
    chat_history_db = {
        "study": [],
        "planner": [],
        "expense": [],
        "content": []
    }
    save_chat_history()
    return {"status": "success"}

@app.post("/api/agents/study/process")
async def process_study(req: StudyRequest):
    try:
        session, session_id = get_or_create_session("study", req.session_id)
        result = await study_agent.process_material(req.content, req.is_image, req.prompt_text, chat_history=session["messages"])
        
        formatted_resp = format_agent_response("study", result)
        user_msg = req.prompt_text if req.prompt_text else ("Attached document/image" if req.is_image or req.content.startswith("JVBERi") else req.content)
        
        user_msg_dict = {
            "sender": "user",
            "text": user_msg,
            "image_base64": req.content if req.is_image else None,
            "is_image": req.is_image
        }
        agent_msg_dict = {
            "sender": "agent",
            "text": formatted_resp,
            "image_base64": None,
            "is_image": False
        }
        actual_session_id = update_session_title_and_append("study", session_id, user_msg_dict, agent_msg_dict)
        if isinstance(result, dict):
            result["session_id"] = actual_session_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/planner/schedule")
async def process_planner(req: PlannerRequest):
    try:
        session, session_id = get_or_create_session("planner", req.session_id)
        result = await planner_agent.generate_schedule(
            req.exam_name, req.exam_date, req.topics_completed, req.syllabus,
            content=req.content, is_image=req.is_image
        )
        formatted_resp = format_agent_response("planner", result)
        user_msg = f"Plan Schedule for {req.exam_name}"
        
        user_msg_dict = {
            "sender": "user",
            "text": user_msg,
            "image_base64": req.content if req.is_image else None,
            "is_image": req.is_image
        }
        agent_msg_dict = {
            "sender": "agent",
            "text": formatted_resp,
            "image_base64": None,
            "is_image": False
        }
        actual_session_id = update_session_title_and_append("planner", session_id, user_msg_dict, agent_msg_dict)
        if isinstance(result, dict):
            result["session_id"] = actual_session_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/expense/process")
async def process_expense(req: ExpenseRequest):
    try:
        session, session_id = get_or_create_session("expense", req.session_id)
        result = await expense_agent.process_receipt(req.image_base64, req.prompt_text)
        formatted_resp = format_agent_response("expense", result)
        user_msg = req.prompt_text if req.prompt_text else "Receipt Upload"
        
        user_msg_dict = {
            "sender": "user",
            "text": user_msg,
            "image_base64": req.image_base64,
            "is_image": True
        }
        agent_msg_dict = {
            "sender": "agent",
            "text": formatted_resp,
            "image_base64": None,
            "is_image": False
        }
        actual_session_id = update_session_title_and_append("expense", session_id, user_msg_dict, agent_msg_dict)
        if isinstance(result, dict):
            result["session_id"] = actual_session_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agents/content/draft")
async def process_content(req: ContentRequest):
    try:
        session, session_id = get_or_create_session("content", req.session_id)
        result = await content_agent.draft_content(req.task, req.context)
        formatted_resp = format_agent_response("content", result)
        
        user_msg_dict = {
            "sender": "user",
            "text": f"Task: {req.task}\nContext: {req.context}",
            "image_base64": None,
            "is_image": False
        }
        agent_msg_dict = {
            "sender": "agent",
            "text": formatted_resp,
            "image_base64": None,
            "is_image": False
        }
        actual_session_id = update_session_title_and_append("content", session_id, user_msg_dict, agent_msg_dict)
        if isinstance(result, dict):
            result["session_id"] = actual_session_id
        return result
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
            session_id = payload.get("session_id") or request.get("session_id")
            
            start_time = time.time()
            result = {}
            status = "success"
            actual_session_id = None
            
            try:
                if agent == "study":
                    is_image = payload.get("is_image", False)
                    content = payload.get("file_base64") or payload.get("content", "")
                    prompt_text = payload.get("prompt_text")
                    
                    session, session_id = get_or_create_session("study", session_id)
                    result = await study_agent.process_material(content, is_image, prompt_text, chat_history=session["messages"])
                    
                    formatted_resp = format_agent_response("study", result)
                    user_msg = prompt_text if prompt_text else ("Attached document/image" if is_image or content.startswith("JVBERi") else content)
                    
                    user_msg_dict = {
                        "sender": "user",
                        "text": user_msg,
                        "image_base64": content if is_image else None,
                        "is_image": is_image
                    }
                    agent_msg_dict = {
                        "sender": "agent",
                        "text": formatted_resp,
                        "image_base64": None,
                        "is_image": False
                    }
                    actual_session_id = update_session_title_and_append("study", session_id, user_msg_dict, agent_msg_dict)
                elif agent == "planner":
                    is_image = payload.get("is_image", False)
                    content = payload.get("file_base64") or payload.get("content")
                    
                    session, session_id = get_or_create_session("planner", session_id)
                    result = await planner_agent.generate_schedule(
                        payload.get("exam_name", ""),
                        payload.get("exam_date", ""),
                        payload.get("topics_completed", []),
                        payload.get("syllabus", []),
                        content=content,
                        is_image=is_image
                    )
                    formatted_resp = format_agent_response("planner", result)
                    user_msg = f"Plan Schedule for {payload.get('exam_name', '')}"
                    
                    user_msg_dict = {
                        "sender": "user",
                        "text": user_msg,
                        "image_base64": content if is_image else None,
                        "is_image": is_image
                    }
                    agent_msg_dict = {
                        "sender": "agent",
                        "text": formatted_resp,
                        "image_base64": None,
                        "is_image": False
                    }
                    actual_session_id = update_session_title_and_append("planner", session_id, user_msg_dict, agent_msg_dict)
                elif agent == "expense":
                    image_base64 = payload.get("image_base64", "")
                    prompt_text = payload.get("prompt_text")
                    
                    session, session_id = get_or_create_session("expense", session_id)
                    result = await expense_agent.process_receipt(
                        image_base64,
                        prompt_text
                    )
                    formatted_resp = format_agent_response("expense", result)
                    user_msg = prompt_text if prompt_text else "Receipt Upload"
                    
                    user_msg_dict = {
                        "sender": "user",
                        "text": user_msg,
                        "image_base64": image_base64,
                        "is_image": True
                    }
                    agent_msg_dict = {
                        "sender": "agent",
                        "text": formatted_resp,
                        "image_base64": None,
                        "is_image": False
                    }
                    actual_session_id = update_session_title_and_append("expense", session_id, user_msg_dict, agent_msg_dict)
                elif agent == "content":
                    task = payload.get("task", "")
                    context = payload.get("context", "")
                    
                    session, session_id = get_or_create_session("content", session_id)
                    result = await content_agent.draft_content(
                        task,
                        context
                    )
                    formatted_resp = format_agent_response("content", result)
                    
                    user_msg_dict = {
                        "sender": "user",
                        "text": f"Task: {task}\nContext: {context}",
                        "image_base64": None,
                        "is_image": False
                    }
                    agent_msg_dict = {
                        "sender": "agent",
                        "text": formatted_resp,
                        "image_base64": None,
                        "is_image": False
                    }
                    actual_session_id = update_session_title_and_append("content", session_id, user_msg_dict, agent_msg_dict)
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
                "session_id": actual_session_id,
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
