# PW1 (Module 1)

**Research Project**: Dynamic Context Curation for Agentic Software Engineering using Runtime Execution Tracing and Model Context Protocol (MCP)

---

## 1. Project Overview
This repository contains Modules 1â€“4 of a larger software engineering research project. The ultimate objective is to build an AI-assisted debugging system that dynamically retrieves runtime state information using the Model Context Protocol (MCP) instead of sending full source files and raw execution traces to an LLM.

**Module 1** provides the foundational **secure code execution engine**, allowing users to write, execute, and inspect Python and Java 17 programs securely inside isolated Docker containers.

> [!NOTE]
> This repository currently implements **Module 1 (Code Execution Engine)** only. Features such as MCP, AI Agents, LLM Integration, Vector DBs, RAG, and Runtime Execution Tracing are intentional non-goals for this module and will be implemented in subsequent project phases.

---

## 2. Current Module Scope
- Web-based code playground supporting **Python 3** and **Java 17**.
- Monaco Code Editor integration with syntax highlighting, line numbers, and language-specific starter code.
- Docker-based sandboxed execution environment.
- FastAPI backend serving structured execution results (stdout, stderr, exit code, execution time, and execution status).

---

## 3. System Architecture

```text
User Selects Language (Python / Java)
              │
              ▼
    Monaco Code Editor (React + Vite)
              │
              │ POST /execute
              ▼
       FastAPI Backend
              │
       CodeExecutionService
              │
  ┌───────────┴───────────┐
  ▼                       ▼
PythonExecutor        JavaExecutor
  │                       │
  └───────────┬───────────┘
              │
              ▼
   Docker Isolated Container
 (Network disabled, 256MB RAM, 1 CPU)
              │
              ▼
   stdout / stderr / exit_code
              │
              ▼
  JSON Result returned to React UI
```

### Directory Structure
```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI entrypoint & CORS
│   │   ├── models/                # Pydantic schemas (ExecutionRequest, ExecutionResponse)
│   │   │   └── execution.py
│   │   ├── routes/                # POST /execute route
│   │   │   └── execution.py
│   │   └── services/              # Executor dispatcher & language implementation
│   │       ├── executor.py
│   │       └── executors/
│   │           ├── base.py        # Abstract Docker sandbox executor
│   │           ├── python_executor.py
│   │           └── java_executor.py
│   ├── docker/
│   │   ├── python/Dockerfile      # Python 3 executor container definition
│   │   └── java/Dockerfile        # Java 17 executor container definition
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx         # App title & subtitle header
│   │   │   ├── LanguageSelector.jsx
│   │   │   ├── RunButton.jsx
│   │   │   ├── CodeEditor.jsx     # Monaco Editor wrapper
│   │   │   └── OutputPanel.jsx    # Formatted status & terminal output
│   │   ├── services/
│   │   │   └── api.js             # Axios API client
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── .env.example
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

---

## 4. Technology Stack

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite
- **Code Editor**: Monaco Editor (`@monaco-editor/react`)
- **HTTP Client**: Axios
- **Icons**: Lucide React
- **Styling**: Vanilla CSS (Custom modern dark developer-tool design system)

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Server**: Uvicorn
- **Validation**: Pydantic v2
- **Container SDK**: Python `docker` SDK

### Sandbox Execution
- **Containerization**: Docker Engine
- **Languages**: Python 3.11, OpenJDK/Eclipse-Temurin 17

---

## 5. Why Docker is Used
Executing untrusted user-submitted code directly on the host operating system poses serious security risks (file system corruption, unauthorized host resource access, malicious network calls). 

Docker is used to create ephemeral, isolated container environments for each execution request. This guarantees that user code runs strictly separated from host files, system processes, and network resources.

---

## 6. Supported Languages & Conventions

### Python
- Executed using `python3 script.py`.
- Temporary script created in sandbox workspace.

### Java 17
- Submitted code must contain a `public class Main` with a `main` method:
  ```java
  public class Main {
      public static void main(String[] args) {
          System.out.println("Hello from Java");
      }
  }
  ```
- Compiled with `javac Main.java` and executed with `java Main`.

---

## 7. Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js v18+ and npm
- Docker Engine / Docker Desktop

### 1. Build Executor Docker Images
From the repository root, execute:

```bash
docker build -t runtime-debugger-python ./backend/docker/python
docker build -t runtime-debugger-java ./backend/docker/java
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
```

---

## 8. Running the Application

### Start the Backend
From the `backend/` folder (with virtualenv activated):

```bash
uvicorn app.main:app --reload --port 8000
```
FastAPI server will be live at `http://localhost:8000`.

### Start the Frontend
From the `frontend/` folder:

```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 9. Example API Request & Response

### Request
`POST /execute`

```json
{
  "language": "python",
  "code": "def main():\n    print('Hello World')\n\nmain()"
}
```

### Successful Response
```json
{
  "status": "success",
  "language": "python",
  "stdout": "Hello World\n",
  "stderr": "",
  "exit_code": 0,
  "execution_time": 0.12
}
```

### Java Compilation Error Response
```json
{
  "status": "compile_error",
  "language": "java",
  "stdout": "",
  "stderr": "Main.java:3: error: ';' expected\n        System.out.println(\"Hello\")\n                                  ^\n1 error\n",
  "exit_code": 1,
  "execution_time": 0.08
}
```

---

## 10. Security Controls & MVP Limitations

### Implemented Sandbox Controls
- `--network none`: Container network access is strictly disabled.
- `--memory 256m`: RAM utilization capped at 256MB.
- `nano_cpus`: CPU core usage restricted to 1.0 core.
- Execution Timeout: Hard limit of 5.0 seconds per execution.
- Non-root User: Execution runs under restricted user `sandboxuser` (UID 1000).
- Automatic Container Cleanup: Containers are forcibly removed after process termination.

### MVP Security Limitations
- This sandbox is an MVP execution isolation layer and is **not** a production-ready multi-tenant sandbox engine (such as gVisor, Firecracker microVMs, or WebAssembly sandboxes).
- Output stream truncation is not enforced for extremely high byte bursts within the 5s window.

---

## 11. Runtime tracing and trace queries (Modules 2 & 3)

Every `POST /execute` response now includes an `execution_id`. The response intentionally does **not** include the potentially large trace. Instead, the trace is held by a replaceable, thread-safe in-memory store and can be queried selectively.

```text
Code -> Executor -> Tracer -> Trace Store -> Query Service -> Future MCP -> Future Debugging Agent
```

Python execution uses a bounded `sys.settrace()` runner in the sandbox. It records program boundaries, function calls/returns, executed lines, exceptions, safe local-variable snapshots, and stack frames. Values are restricted to small, JSON-safe representations. Java uses the same language-independent event schema and produces useful MVP program, method, compilation-diagnostic, and runtime-exception events from JVM output/source metadata; it deliberately does not expose JVM internals.

The common event fields are event ID, type, language, source file/line, function, relative timestamp, stack, safe variables, and optional exception. Collection is bounded (2,000 events per execution); truncation is retained as metadata.

Available REST queries:

- `GET /executions/{id}` — execution metadata only
- `GET /executions/{id}/error`, `/stack`, `/frames/{frame_id}/variables`
- `GET /executions/{id}/source?file=script.py&line=10&radius=3`
- `GET /executions/{id}/path?max_events=100`
- `GET /executions/{id}/events/{event_id}`
- `POST /executions/{id}/search` — accepts `event_type`, `function`, `variable`, `exception_type`, `file`, `line_start`, `line_end`, and `max_results`

This selective-query design avoids providing a full source file or full runtime trace unless a caller explicitly requests a narrow source region or a bounded path.

---

## 12. MCP debugging server (Module 4)

MCP is a local, standard tool interface for a future debugging agent. It exposes the same read-only `TraceQueryService` used by RESTâ€”it does not execute code, access the filesystem, or create a second trace store.

```text
Tracer
  â†“
Trace Store
  â†“
Trace Query Service
  â†“
MCP
  â†“
Future Agent
```

Available tools are `get_error_context`, `get_stack_trace`, `get_frame_variables`, `get_source_context`, `get_execution_path`, `get_event`, and `search_trace`. They return targeted, bounded context; in particular source requests return a specified line range and execution-path/search results are capped.

For the current in-memory trace store, start the FastAPI process so MCP and `/execute`
share the same trace data:

```bash
uvicorn app.main:app --reload --port 8000
```

The MCP Streamable HTTP endpoint is `http://localhost:8000/mcp`. The standalone
`python -m app.mcp.server` command remains useful for stdio-client development,
but it has a separate in-memory store and therefore cannot query executions made
by a separately running FastAPI process.

### Quick MCP Inspector check

With the backend still running, open a second terminal from the project root and run:

```bash
cd backend
npx @modelcontextprotocol/inspector --server-url http://localhost:8000/mcp --transport http
```

In the Inspector browser page, select the server and click **Connect**, then open
**Tools** to confirm the seven debugging tools are discovered. First use
`POST /execute` in `http://localhost:8000/docs` to run code and copy the returned
`execution_id`. Paste that ID into a tool call such as `get_error_context` or
`get_stack_trace`. Do not open `/mcp` directly in a browser: the MCP client manages
the required protocol session automatically.

For a manual test, first submit the following to `POST /execute` and retain its `execution_id`:

```python
def divide(a, b):
    return a / b

def process():
    return divide(10, 0)

process()
```

Connect an MCP client over stdio, discover the listed tools, then call `get_error_context`, `get_stack_trace`, `get_frame_variables` with the failing frame ID, and `get_source_context` with `script.py`, line `2`, and a small radius. `get_execution_path`, `get_event`, and `search_trace` provide further selective inspection. Each call records structured telemetry (tool, execution ID, duration, result size, success, and event count) through the backend logger.

**The debugging agent and automatic repair are NOT implemented yet.** Module 4 only makes runtime context available to a future agent without returning the complete trace by default.
