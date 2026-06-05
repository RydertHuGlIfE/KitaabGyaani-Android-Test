# KitaabGyaani Architecture

## System Overview

KitaabGyaani is a **local-first multi-agent system** where the Android phone serves as the interface and the laptop runs all backend processing. The iQOO Office Kit acts as the network bridge enabling seamless handoff between devices.

```
┌─────────────────────────────────────────────────────────────┐
│                    KITAABGYAANI STACK                       │
├─────────────────────────────────────────────────────────────┤
│ INTERFACE LAYER      │ BRIDGE LAYER      │ PROCESSING LAYER │
│ ─────────────────────┼──────────────────┼──────────────────│
│ Android App (iQOO)   │ Office Kit        │ Laptop Backend   │
│ • Camera (CameraX)   │ • WebSockets      │ • FastAPI        │
│ • Voice (STT)        │ • Request Queue   │ • Ollama (Local) │
│ • MediaPipe (Focus)  │ • Real-time Sync  │ • Groq API       │
│ • Touch UI           │ • Auth Bridge     │ • Agent Router   │
│ • Notifications      │ • Fallback Queue  │ • Database       │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture Layers

### 1. **Interface Layer (Android Phone)**

The phone is **purely a client interface**. No heavy processing, no agent logic.

#### Components:
- **UI Layer** (Jetpack Compose)
  - Study dashboard
  - Planner view
  - Focus session timer
  - Expense tracker
  - Content drafting panel

- **Camera Module** (CameraX + MediaPipe)
  - Optical character recognition (OCR) via laptop
  - Focus Agent monitoring (eye detection, head pose)
  - Receipt/document scanning

- **Audio Stack**
  - **Speech-to-Text (STT)**: Google Speech Recognition Intent (built-in, Hindi+English)
  - **Text-to-Speech (TTS)**: Android TextToSpeech API (built-in, multilingual)
  - Voice assistant input → sent to laptop for agent processing

- **Notifications**
  - Drowsiness alerts (from Focus Agent)
  - Study reminders (from Planner Agent)
  - Schedule updates
  - Real-time push notifications via WebSocket

#### Tech Stack:
- **Language**: Kotlin
- **UI Framework**: Jetpack Compose
- **Camera**: CameraX
- **ML On-Device**: MediaPipe (face detection, pose estimation)
- **HTTP Client**: Retrofit + OkHttp
- **WebSocket**: OkHttp WebSocket
- **Local Storage**: SQLite / Room Database
- **Networking**: WiFi direct or Office Kit bridge

---

### 2. **Bridge Layer (iQOO Office Kit)**

The Office Kit provides the **communication bridge** between phone and laptop.

#### Responsibilities:
- **Request Routing**: Phone → Laptop → Phone
- **WebSocket Management**: Real-time bi-directional communication
- **Request Queueing**: Handle offline scenarios, retry failed requests
- **Authentication**: Secure device pairing
- **Fallback Handling**: If laptop is offline, queue requests and sync when available
- **Data Serialization**: JSON request/response protocol

#### Communication Protocol:
```json
REQUEST (Phone → Laptop)
{
  "id": "req_12345",
  "timestamp": 1234567890,
  "agent": "study",
  "action": "generate_summary",
  "payload": {
    "file_path": "DBMS_Chapter3.pdf",
    "file_base64": "JVBERi0xLjQKJeLj...",
    "options": {
      "summary_length": "short",
      "language": "en"
    }
  }
}

RESPONSE (Laptop → Phone)
{
  "request_id": "req_12345",
  "status": "success",
  "agent": "study",
  "data": {
    "summary": "...",
    "flashcards": [...],
    "mcqs": [...]
  },
  "processing_time_ms": 4200,
  "server_timestamp": 1234567920
}
```

#### Tech Stack:
- **Protocol**: WebSocket over WiFi
- **Port**: 8765 (configurable)
- **Format**: JSON
- **Auth**: Device token + HMAC signature
- **Encryption**: TLS 1.3 (optional for local networks)

---

### 3. **Processing Layer (Laptop Backend)**

The laptop runs **all agent logic and heavy computation**.

#### Architecture:

```
┌──────────────────────────────────────────────────────────────┐
│                    FASTAPI SERVER (8000)                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              REQUEST HANDLER (WebSocket)              │ │
│  │ • Parse incoming requests                             │ │
│  │ • Validate & authenticate                             │ │
│  │ • Route to appropriate agent                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            AGENT ORCHESTRATOR / ROUTER                │ │
│  │                                                        │ │
│  │  Study Agent      Planner Agent    Focus Agent        │ │
│  │  Expense Agent    Content Agent                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              LLM & PROCESSING LAYER                   │ │
│  │                                                        │ │
│  │  ┌──────────────┐        ┌──────────────┐            │ │
│  │  │   Ollama     │        │  Groq API    │            │ │
│  │  │ (Local LLM)  │        │  (Cloud LLM) │            │ │
│  │  │ Qwen2.5 3B   │        │  Backup Fast │            │ │
│  │  │ RTX 3050 6GB │        │  Processing  │            │ │
│  │  └──────────────┘        └──────────────┘            │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            RESPONSE FORMATTER & CACHE                 │ │
│  │ • Format results                                       │ │
│  │ • Cache common queries                                │ │
│  │ • Send back to phone                                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │          WEBSOCKET RESPONSE (→ Phone)                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

### Study Agent
**Purpose**: Extract knowledge from documents → summaries, flashcards, MCQs

**Flow**:
1. Phone sends: PDF file (base64) + OCR'd notebook page
2. Laptop receives: File → stores temp
3. Study Agent:
   - OCR extraction (if image)
   - Text chunking
   - Prompt to Ollama/Groq: "Extract key concepts, generate flashcards..."
   - Post-processing: Format into structured JSON
4. Response: `{ summary, flashcards[], mcqs[], concept_map }`

**LLM Choice**:
- **Fast queries** (< 500 tokens): Ollama local (sub-2s)
- **Long documents** (> 500 tokens): Groq API (backup)

---

### Planner Agent
**Purpose**: Generate study schedules based on exam dates & syllabus

**Flow**:
1. Phone sends: `{ exam_date, syllabus_topics[], current_progress }`
2. Planner Agent:
   - Calculate days remaining
   - Fetch Study Agent output (what topics are done)
   - Prompt to LLM: "Create day-by-day study schedule..."
   - Return: Day-by-day breakdown with recommended topics per day
3. Response: `{ schedule: [{ day, topics, duration_hours }], milestones }`

**Storage**: Cached in local DB, synced to phone

---

### Focus Agent
**Purpose**: Monitor study quality in real-time via camera

**Flow**:
1. Phone: Front camera stream (local processing via MediaPipe)
2. MediaPipe detects:
   - Eyes closed → drowsiness
   - Head out of frame → distraction
   - Repeated inattention → suggest break
3. On-device detection → instant notification (no latency)
4. Laptop logs: Focus metrics for dashboard

**Tech**: MediaPipe (on-device), zero cloud dependency

---

### Expense Agent
**Purpose**: OCR receipts → auto-categorize spending

**Flow**:
1. Phone sends: Receipt photo (base64)
2. Laptop:
   - OCR extraction (Tesseract or similar)
   - Parse: amount, merchant, date
   - Prompt to LLM: "Categorize this: Food / Books / Transport / etc."
3. Response: `{ amount, category, merchant, date, confidence }`

**Storage**: Logged to expense DB, weekly summary pushed to phone

---

### Content Agent
**Purpose**: Draft emails, applications, reports

**Flow**:
1. Phone sends: `{ task: "Write internship application", context: "...company name, position..." }`
2. Laptop Content Agent:
   - Build prompt with context
   - Send to Groq (for quality, not speed)
   - Return: Draft email/application
3. Response: `{ draft_text, suggestions: [], tone: "formal" }`

**Note**: Runs on Groq (more reliable for long-form, not time-critical)

---

## Data Flow Examples

### Example 1: Upload PDF → Get Study Kit

```
STEP 1: Phone captures PDF
─────────────────────────
User: "Take a photo of DBMS_Chapter3.pdf"
Phone: Sends base64 of PDF (or scanned image)
       POST /api/agents/study/process
       Payload: { file: "base64...", action: "full_kit" }

STEP 2: Laptop processes
─────────────────────────
FastAPI: Receives request
Study Agent: Extracts text
Ollama: Generates summary (local, sub-5s)
Ollama: Creates 15 flashcards (local)
Ollama: Creates 10 MCQs (local)
Format: JSON with all three outputs

STEP 3: Response to phone
─────────────────────────
WebSocket SEND:
{
  "request_id": "req_xyz",
  "status": "success",
  "agent": "study",
  "data": {
    "summary": "DBMS covers...",
    "flashcards": [
      { "q": "What is normalization?", "a": "..." },
      ...
    ],
    "mcqs": [
      { "q": "Question", "options": ["A", "B", "C", "D"], "answer": "B" },
      ...
    ]
  },
  "processing_time_ms": 4200
}

Phone: Displays in Study dashboard
       Stores in local SQLite
```

### Example 2: Create Study Schedule

```
STEP 1: Planner request
─────────────────────────
User: "I have DBMS exam in 12 days"
Phone: Sends exam_date + current_topics_done
       POST /api/agents/planner/schedule
       Payload: { exam_date: "2026-06-17", topics_completed: ["Chapter 1", "Chapter 2"], exam_name: "DBMS" }

STEP 2: Planner Agent processes
─────────────────────────────────
Fetch Study Agent progress (from Study Agent cache)
Calculate: 12 days - 2 days done = 10 days left
5 remaining chapters / 10 days = ~0.5 chapters/day
Prompt to Ollama:
  "I have 10 days to study 5 chapters of DBMS. Create a day-by-day schedule with focus areas."
LLM returns structured plan

STEP 3: Response to phone
──────────────────────────
{
  "request_id": "req_abc",
  "status": "success",
  "agent": "planner",
  "data": {
    "exam_name": "DBMS",
    "exam_date": "2026-06-17",
    "schedule": [
      {
        "day": 1,
        "date": "2026-06-06",
        "topics": ["Normalization (Part 1)"],
        "duration_hours": 2,
        "study_load": "medium",
        "resources": ["Chapter 3", "Video: DB Normalization"]
      },
      {
        "day": 2,
        "date": "2026-06-07",
        "topics": ["Normalization (Part 2)"],
        "duration_hours": 2,
        "study_load": "medium"
      },
      ...
    ],
    "milestones": [
      { "day": 3, "milestone": "Complete 1st half of syllabus" }
    ]
  }
}

Phone: Shows day-by-day plan
       Sends daily reminders via notifications
       Updates when user marks topics as done
```

### Example 3: Real-time Focus Monitoring

```
CONTINUOUS PROCESS (Phone + Laptop)
────────────────────────────────────

Phone (MediaPipe, on-device):
  • Starts study session
  • Front camera active
  • Detects: eyes open ✓, head in frame ✓, face visible ✓
  
  At t=120s: Eyes closed for 3s
  → Trigger: Drowsiness alert
  → Phone shows: "⚠️ Stay focused! Take a break?"
  
  At t=300s: Session ends
  → Phone sends focus_session log to laptop
  
Laptop (Focus Agent):
  • Receives session log
  • Calculates: focus_score = (focused_seconds / total_seconds) * 100
  • Updates dashboard metrics
  • Logs to DB for historical analysis

Phone Dashboard Shows:
  • Total focus time: 5m 20s
  • Focus score: 89%
  • Alerts: 2 drowsiness alerts
  • Recommendation: "Great focus! Keep it up."
```

---

## Technology Stack Summary

### Phone (Android)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Kotlin | Native Android dev |
| UI | Jetpack Compose | Modern declarative UI |
| Camera | CameraX | Abstracted camera API |
| ML | MediaPipe | On-device focus detection |
| STT | Google Speech API | Voice input |
| TTS | Android TextToSpeech | Voice output |
| Networking | Retrofit + OkHttp | HTTP + WebSocket |
| Database | Room (SQLite) | Local caching |

### Laptop (Backend)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.10+ | Server logic |
| Framework | FastAPI | Async HTTP + WebSocket server |
| Local LLM | Ollama + Qwen2.5 3B | Sub-5s text generation |
| Cloud LLM | Groq API | Fast backup LLM |
| OCR | Tesseract / EasyOCR | Document text extraction |
| Database | SQLite / PostgreSQL | Persistent storage |
| Task Queue | Celery (optional) | Async task processing |
| File Storage | Local disk / iCloud | Cache PDFs, images |

### Bridge (iQOO Office Kit)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Protocol | WebSocket + REST | Real-time + request-response |
| Port | 8765 (configurable) | Server port |
| Format | JSON | Request/response serialization |
| Auth | HMAC tokens | Device pairing & security |
| TLS | Optional (local network) | Encryption |

---

## Request/Response Cycle (Complete)

```
TIME    DEVICE       ACTION
─────────────────────────────────────────────────────────────
t=0ms   PHONE        User uploads PDF to Study Agent
        [Camera captures PDF image]

t=50ms  PHONE        Sends POST /api/agents/study/process
        [Base64 encoded image + metadata]

t=55ms  OFFICE_KIT   Receives request
        [Queues in router]

t=60ms  LAPTOP       FastAPI receives from Office Kit
        [Validates request, extracts PDF text]

t=100ms LAPTOP       Routes to Study Agent
        [Study Agent loads request]

t=150ms LAPTOP       Calls Ollama for summary
        [Queues LLM request to local model]

t=2150ms OLLAMA      Returns summary (2s inference)
        [Study Agent receives, processes]

t=2200ms LAPTOP      Calls Ollama for flashcards
        [LLM generates Q&A pairs]

t=3200ms OLLAMA      Returns flashcards (1s inference)
        [Study Agent formats response]

t=3250ms LAPTOP      Calls Ollama for MCQs
        [LLM generates multiple choice]

t=4250ms OLLAMA      Returns MCQs (1s inference)
        [Study Agent packages all three]

t=4300ms LAPTOP      Response ready
        [FastAPI sends via WebSocket]

t=4350ms OFFICE_KIT  Routes response to phone
        [WebSocket delivery]

t=4400ms PHONE       Receives complete study kit
        [UI renders: summary + flashcards + MCQs]

═════════════════════════════════════════════════════════════
TOTAL LATENCY: ~4.4 seconds (sub-5s achieved!)
```

---

## Offline & Fallback Strategy

### Scenario: Laptop is offline

```
Phone: Requests PDF summary
       Office Kit can't reach laptop
       Status: QUEUED

Action:
  1. Store request in local SQLite queue
  2. Show user: "Processing offline - will sync when connected"
  3. Display any cached results from previous runs

When laptop comes online:
  1. Office Kit pushes queued requests
  2. Laptop processes in order
  3. Results pushed back to phone
  4. Phone updates UI
```

### Scenario: Groq API fails

```
Laptop receives: "Generate content for email"
Attempts Groq call → TIMEOUT / API error

Fallback:
  1. Try local Ollama (slower but always available)
  2. If Ollama also fails → return partial results / prompt user
  3. Queue for retry on next Groq availability
```

---

## Performance Optimization

### Local LLM (Ollama)
- **Model**: Qwen2.5 3B (3 billion parameters)
- **VRAM**: 3-4GB (fits in RTX 3050 6GB)
- **Latency**: Sub-2s per request
- **Use Case**: Summary generation, flashcard creation, quick MCQs

### Groq API
- **Latency**: 200-500ms per request
- **Use Case**: Long-form content, backup when local fails
- **Cost**: Free tier available
- **Fallback Priority**: High

### Caching Strategy
```
Phone Cache:
  ✓ Study summaries (last 10 PDFs)
  ✓ Planner schedules (current + previous 5)
  ✓ Focus metrics (last 30 days)

Laptop Cache:
  ✓ Common prompts + responses (LRU, 1000 entries)
  ✓ User preference profiles
  ✓ Exam/syllabus data
```

---

## Security & Privacy

### Data Flow Security
- **Phone ↔ Laptop**: HTTPS/WSS (TLS 1.3 on local network)
- **Laptop ↔ Groq**: HTTPS with API key
- **Groq ↔ Laptop**: No user data sent (only text to process)

### Privacy Guarantees
- **On-Device Focus Detection**: Zero data leaves phone (MediaPipe runs locally)
- **No Cloud Sync**: Study data stays on phone + laptop (unless user opts in)
- **Offline-First**: All core features work without internet

### Device Pairing
- Initial pairing: QR code or manual token exchange
- Subsequent requests: HMAC signature validation
- Token rotation: Periodic refresh (optional)

---

## Deployment Checklist

### Laptop Setup
```bash
# 1. Install Python 3.10+
# 2. Clone KitaabGyaani backend
# 3. Install dependencies
pip install fastapi uvicorn ollama groq

# 4. Download Ollama + Qwen2.5 3B model
ollama pull qwen2.5:3b

# 5. Start Ollama service
ollama serve

# 6. Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000

# 7. Configure Office Kit bridge (IP, port, token)
# 8. Test connection from phone
```

### Phone Setup
```
1. Install KitaabGyaani Android app (from APK or Play Store)
2. Open app → Settings → Server Configuration
3. Enter laptop IP + port (e.g., 192.168.1.100:8000)
4. Scan QR code or enter pairing token
5. Test: Upload a PDF → verify summary appears
```

---

## Future Enhancements

- [ ] Multi-device sync (tablet, smartwatch)
- [ ] Collaborative study rooms (real-time with friends)
- [ ] Advanced analytics (learning patterns, weak topics)
- [ ] Integration with calendar (auto-block study time)
- [ ] Voice-guided study sessions
- [ ] Gamification (badges, study streaks)
- [ ] Export to Anki, Quizlet
- [ ] Support for video lectures (YouTube, Coursera)