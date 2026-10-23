# Project Documentation

A practical setup, operational, and debugging guide for developers and researchers working on the PW1 runtime debugging and evaluation platform.

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Prerequisites](#2-prerequisites)
- [3. Clone the Repository](#3-clone-the-repository)
- [4. Project Structure](#4-project-structure)
- [5. Environment Configuration](#5-environment-configuration)
- [6. Backend Setup](#6-backend-setup)
- [7. Frontend Setup](#7-frontend-setup)
- [8. Docker / Execution Environment](#8-docker--execution-environment)
- [9. Running the Project](#9-running-the-project)
- [10. Basic Usage](#10-basic-usage)
- [11. M8 Evaluation Usage](#11-m8-evaluation-usage)
- [12. Benchmark Dataset](#12-benchmark-dataset)
- [13. API / Backend Endpoints](#13-api--backend-endpoints)
- [14. Troubleshooting](#14-troubleshooting)
- [15. CI/CD](#15-cicd)
- [16. Development Notes](#16-development-notes)
- [17. Quick Start](#17-quick-start)
- [18. Logs and M8 Artifacts](#18-logs-and-m8-artifacts)
- [19. Tracing the Logging Flow](#19-tracing-the-logging-flow)
- [20. Fresh Evaluation / Dataset Reset](#20-fresh-evaluation--dataset-reset)
- [21. MCP Debugging](#21-mcp-debugging)
- [22. Important MCP & Debug REST Endpoints](#22-important-mcp--debug-rest-endpoints)
- [23. Debugging Workflow](#23-debugging-workflow)
- [24. MCP Tools Reference](#24-mcp-tools-reference)
- [25. Practical Debugging Walkthrough](#25-practical-debugging-walkthrough)

---

## 1. Project Overview

This project is an interactive execution and runtime debugging environment. It combines an isolated code execution engine, detailed execution tracing, a Model Context Protocol (MCP) server for selective trace queries, and an AI debugging agent capable of automated diagnosis and repair.

In practical terms, the system allows a developer to:
- Write or load code in a browser-based Monaco editor.
- Execute code securely inside sandboxed containers or local process fallbacks.
- Capture step-by-step runtime events (line execution, function calls, returns, variable states, and exceptions).
- Interactively diagnose and repair runtime bugs using an AI agent.
- Run experimental evaluations (Milestone 8) comparing **Baseline (Full Context)** vs **Dynamic (Curated Context via MCP)** on a benchmark suite.

---

## 2. Prerequisites

Ensure the following tools are installed on your development machine:

- **Git**: For version control (`git --version`)
- **Docker & Docker Compose**: Docker Desktop / Docker Engine with Compose v2+ (`docker --version`, `docker compose version`) for one-command startup and sandboxed container execution.
- **Python** *(Optional if using Docker Compose)*: Version 3.10 or higher (recommended 3.11+) (`python --version`) for running the backend manually without Docker.
- **Node.js & npm** *(Optional if using Docker Compose)*: Node.js 18+ and npm 9+ (`node --version`, `npm --version`) for running the frontend manually without Docker.
- **OpenRouter API Key** *(Optional, required for AI debugging/evaluation features)*: An API key from [OpenRouter](https://openrouter.ai/) for LLM reasoning.

---

## 3. Clone the Repository

Clone the project repository using Git:

```bash
git clone https://github.com/kamalesh2602/PW1.git
cd PW1
```

---

## 4. Project Structure

The repository is organized into two primary applications:

```text
PW1/
├── .github/
│   └── workflows/
│       └── ci-cd.yml          # GitHub Actions workflow for push verification
├── backend/
│   ├── app/
│   │   ├── agent/             # Debugging agent, fixer agent, curator, LLM client
│   │   ├── evaluation/        # M8 benchmark definitions, evaluator service, logger
│   │   ├── mcp/               # Model Context Protocol (MCP) query server
│   │   ├── models/            # Pydantic data schemas (execution, trace, evaluation)
│   │   ├── routes/            # FastAPI route handlers (execution, traces, debug, fix)
│   │   └── services/          # Execution dispatcher, Docker/fallback executors, tracer
│   ├── data/
│   │   ├── m8/                # Evaluation experiment data (m8_experiments.csv, events.jsonl)
│   │   │   └── experiments/   # Per-evaluation run packages (summary, baseline, dynamic, events)
│   │   ├── m8_events.jsonl    # Legacy root event log (preserved for compatibility)
│   │   └── m8_experiments.csv # Legacy root experiment dataset (preserved for compatibility)
│   ├── docker/
│   │   ├── java/              # Dockerfile for Java sandbox runtime
│   │   └── python/            # Dockerfile for Python sandbox runtime
│   ├── logs/
│   │   └── app.log            # General operational application logs
│   ├── tests/                 # Backend pytest test suite
│   ├── .env.example           # Template for backend environment variables
│   ├── Dockerfile             # Container definition for running backend
│   ├── requirements.txt       # Python package dependencies
│   └── README.md              # Backend-specific notes
├── frontend/
│   ├── src/
│   │   ├── components/        # React UI components (Editor, TraceTimeline, EvaluationSection)
│   │   ├── services/          # API client services (axios communication with backend)
│   │   ├── App.jsx            # Main application layout and tab navigation
│   │   └── index.css          # Core design system and visual styling
│   ├── .env.example           # Template for frontend environment variables
│   ├── package.json           # Frontend dependencies and npm scripts
│   └── vite.config.js         # Vite bundler and dev server configuration
├── documentation.md           # Developer setup and operational guide (this file)
└── README.md                  # Research overview and project presentation
```

---

## 5. Environment Configuration

### Backend Environment (`backend/.env`)

In the `backend/` directory, create a `.env` file by copying the provided template:

```bash
cd backend
cp .env.example .env
```

On Windows PowerShell:
```powershell
cd backend
Copy-Item .env.example .env
```

Configure the following variables according to your local environment:

| Variable | Default Value | Description |
|:---|:---|:---|
| `PORT` | `8000` | Port on which the FastAPI server listens |
| `HOST` | `0.0.0.0` | Bind host address for the server |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed frontend origins |
| `PYTHON_IMAGE` | `runtime-debugger-python` | Name of the Docker image used for Python execution |
| `JAVA_IMAGE` | `runtime-debugger-java` | Name of the Docker image used for Java execution |
| `EXECUTION_TIMEOUT`| `5.0` | Maximum allowed execution time in seconds per run |
| `MAX_MEMORY` | `256m` | Maximum container memory limit |
| `MAX_CPUS` | `1.0` | Maximum container CPU limit |
| `TRACE_MAX_EVENTS` | `2000` | Maximum trace events captured per run to prevent runaway loops |
| `TRACE_MAX_SOURCE_RADIUS` | `50` | Maximum radius of source lines returned around a location |
| `TRACE_MAX_QUERY_EVENTS` | `500` | Upper limit for events returned in path queries |
| `OPENROUTER_API_KEY` | *(empty)* | Your OpenRouter API key for LLM diagnosis and repair |
| `LLM_MODEL` | `openrouter/free` | Model identifier used by OpenRouter client |
| `MAX_CONTEXT_CALLS` | `10` | Maximum MCP query budget for the dynamic context curator |
| `MAX_CONTEXT_EVENTS`| `50` | Maximum events returned in curator path exploration |
| `MAX_CONTEXT_LINES` | `100` | Maximum lines returned in curator source inspection |

> **Important**: Never commit your real API keys or secrets to Git.

### Frontend Environment (`frontend/.env`)

In the `frontend/` directory, create a `.env` file by copying the template:

```bash
cd ../frontend
cp .env.example .env
```

On Windows PowerShell:
```powershell
cd ..\frontend
Copy-Item .env.example .env
```

Configure the following Vite variable:

| Variable | Default Value | Description |
|:---|:---|:---|
| `VITE_API_URL` | `http://localhost:8000` | Base URL of the backend FastAPI service |

---

## 6. Backend Setup

Follow these steps to set up and start the backend service:

### 1. Navigate to the backend directory
```bash
cd backend
```

### 2. Create and activate a virtual environment
- **Linux/macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```cmd
  python -m venv venv
  .\venv\Scripts\activate.bat
  ```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the FastAPI server
```bash
uvicorn app.main:app --reload --port 8000
```

The backend server will start at:
- **API URL**: `http://localhost:8000`
- **Swagger Documentation**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
- **MCP Server Endpoint**: `http://localhost:8000/mcp`

---

## 7. Frontend Setup

Follow these steps to set up and start the frontend user interface:

### 1. Navigate to the frontend directory
```bash
cd frontend
```

### 2. Install npm dependencies
```bash
npm install
```

### 3. Start the Vite development server
```bash
npm run dev
```

The frontend application will be live at:
- **Local URL**: `http://localhost:5173`

---

## 8. Docker / Execution Environment

The system provides two deployment and execution models:
1. **Docker Compose**: Orchestrates the entire application (Vite frontend, FastAPI backend with integrated MCP server) using a single command.
2. **Containerized Sandboxes**: Isolates user-submitted Python and Java code from the host machine using unprivileged containers.

### Docker Compose Architecture
The root `docker-compose.yml` configures two coordinated services:
- **`backend`**: FastAPI application running on port `8000`. Mounts `./backend/data` to persist M8 evaluation datasets, `./backend/logs` for operational logging, and `/var/run/docker.sock` to manage execution sandboxes. The Model Context Protocol (MCP) server runs in-process inside FastAPI at `/mcp`.
- **`frontend`**: Vite/React interface running on port `5173` bound to `0.0.0.0`. Communicates with the backend at `http://localhost:8000` (browser-accessible host address).

### Docker Daemon Socket Access & Security Implications
To launch execution sandboxes from within the containerized backend, the backend service mounts the host Docker socket:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```
> [!WARNING]
> **Security Implications**: Mounting `/var/run/docker.sock` grants the backend container full administrative access to the host Docker daemon.
> - **Sandbox Safeguards**: The backend uses this privilege strictly to launch isolated, unprivileged sandbox containers with network disabled (`--network none`), limited memory (`256MB`), limited CPU (`1.0`), and non-root execution (`sandboxuser`, UID 1000).
> - **Environment Scope**: Because Docker socket access allows arbitrary container operations on the host, this configuration is intended for local research and development environments. Do not expose the backend directly to untrusted public networks without an authentication proxy.

### Sandbox Images
The repository defines two sandbox container images in `backend/docker/`:
1. **Python Sandbox (`runtime-debugger-python`)**:
   - Dockerfile: `backend/docker/python/Dockerfile`
   - Base image: `python:3.11-slim`
   - User: Non-root user `sandboxuser` (UID 1000)
2. **Java Sandbox (`runtime-debugger-java`)**:
   - Dockerfile: `backend/docker/java/Dockerfile`
   - Base image: `eclipse-temurin:17-jdk-alpine`
   - User: Non-root user `sandboxuser` (UID 1000)

### Building the Sandbox Images Locally
Before running containerized code execution, build the sandbox images:

```bash
# Build the Python sandbox image
docker build -t runtime-debugger-python backend/docker/python

# Build the Java sandbox image
docker build -t runtime-debugger-java backend/docker/java
```

### Local Fallback Mode
If Docker is not running or sandbox images are not built, the backend automatically uses **local subprocess fallback execution** (`sys.executable` and local `javac`/`java`). This ensures immediate functionality without Docker installed.

---

## 9. Running the Project

You can run the project either using **Docker Compose** (recommended for one-command startup) or **manually in separate terminals**.

### Option A: One-Command Startup with Docker Compose (Recommended)

Start the entire application (frontend, backend, and MCP server) with:

```bash
docker compose up --build
```

#### Accessing the Application
- **Frontend UI**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`
- **Health Check**: `http://localhost:8000/health`
- **Interactive API Docs (Swagger)**: `http://localhost:8000/docs`
- **MCP Server Endpoint**: `http://localhost:8000/mcp`

#### Viewing Logs
View real-time aggregated logs or stream a specific service:

```bash
# View all logs in real-time
docker compose logs -f

# View backend logs only
docker compose logs -f backend

# View frontend logs only
docker compose logs -f frontend
```

#### Stopping the Services
To stop and remove containers while preserving persistent data:

```bash
docker compose down
```

#### Rebuilding After Changes
If you update dependencies or source code:

```bash
docker compose up --build
```

### Option B: Manual Setup Without Docker Compose

If you prefer running services directly on your host machine:

#### Terminal 1 — Backend
```bash
cd backend
# Activate virtual environment
# Linux/macOS: source venv/bin/activate
# Windows PowerShell: .\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

#### Terminal 2 — Frontend
```bash
cd frontend
npm run dev
```

#### Accessing the Application
Navigate to `http://localhost:5173` in your browser.

---

## 10. Basic Usage

The standard user workflow follows these steps:

1. **Open the Interface**: Visit `http://localhost:5173` in your browser.
2. **Select Language & Enter Code**:
   - Choose **Python** or **Java** from the language selector.
   - Enter your code directly into the Monaco editor or select from preset samples.
3. **Execute the Code**:
   - Click the **Run Code** button.
   - The application sends the code to `/execute` and streams execution results.
4. **Inspect Execution & Tracing**:
   - Review terminal output (stdout, stderr, exit code).
   - Use the **Timeline / Trace Explorer** tab to inspect captured execution steps, line executions, stack frames, and local variable values.
5. **Diagnose & Repair Bugs**:
   - If an error occurs, click **Diagnose** to prompt the AI debugging agent for a root-cause explanation and suggested fix.
   - Click **Fix Bug** to trigger the automated repair loop, which tests and validates the proposed candidate patch.
6. **Access Evaluation Mode**:
   - Click the **Evaluation** tab in the navigation header to open the Benchmark Evaluation suite.

---

## 11. M8 Evaluation Usage

The Milestone 8 (M8) evaluation tab is designed to compare two debugging paradigms:
- **Baseline (Full Context)**: Passes the entire source code and complete raw execution trace directly to the debugging LLM.
- **Dynamic (Curated Context via MCP)**: Starts with minimal failure context, then uses an autonomous Context Curator agent to retrieve only necessary stack frames, source lines, and variable values via MCP tools before querying the debugging LLM.

### Key Concepts

| Concept | Explanation |
|:---|:---|
| **Benchmark Definition** | Fixed, immutable bug specification stored in code (`backend/app/evaluation/benchmarks.py`). Contains the code, bug category, expected failure, root cause, and expected behavior. |
| **Baseline Mode** | Full source code + full execution trace passed directly to the LLM without MCP tools. |
| **Dynamic Mode** | Minimal seed -> M7 Dynamic Context Curator -> iterative MCP queries -> curated context -> LLM. |
| **Experiment Record** | An empirical measurement generated **only** when an evaluation is explicitly executed. Logs token counts, context size, latency, MCP calls, root cause identification, and fix correctness. |

### Conducting an Evaluation

1. Open the **Benchmark Evaluation** tab in the UI.
2. Select a benchmark from the dropdown (e.g. `B001`, `B002`, ..., `B010`).
   > **Note**: Selecting or loading a benchmark into the editor does **NOT** run an experiment or write any records.
3. Click the **Run Paired Evaluation** button.
4. The system executes both Baseline and Dynamic runs in sequence, capturing side-by-side telemetry:
   - Context size comparison (character count and percentage reduction)
   - Token consumption comparison (input, output, and total tokens)
   - Tool call overhead and latency measurements
   - Diagnostic and repair success validation
5. Review the resulting side-by-side comparison card and inspect individual event logs.
6. To export experiment data, click **Export CSV** to download `m8_experiments.csv`.

> **Important**: `backend/data/m8/m8_experiments.csv` contains experiment results generated from runs. It is not the benchmark definition itself.

---

## 12. Benchmark Dataset

Benchmark definitions are maintained in:
```text
backend/app/evaluation/benchmarks.py
```

Each benchmark is represented as a structured `BenchmarkCase` object with the following metadata:

- **`bug_id` / `id`**: Unique benchmark identifier (`B001` through `B010`)
- **`title`**: Descriptive name of the scenario
- **`category` / `bug_category`**: Target bug category
- **`language`**: Programming language (`python`)
- **`code` / `source_code`**: Complete executable Python source code reproducing the bug
- **`stdin`**: Standard input string (empty if unneeded)
- **`expected_error` / `expected_failure`**: Expected exception or failure type
- **`expected_root_cause`**: Specific explanation of the underlying flaw
- **`expected_behavior`**: Exact expected behavior and output of the corrected program

### Suite Summary (B001 – B010)

| ID | Title | Bug Category | Expected Failure | OOP? |
|:---|:---|:---|:---|:---:|
| `B001` | Division by Zero in Function Call | `ZeroDivisionError` | `ZeroDivisionError` | No |
| `B002` | Rank Index Calculation Exceeds Bounds | `IndexError` | `IndexError` | No |
| `B003` | Missing Authentication Header Key | `KeyError` | `KeyError` | No |
| `B004` | String and Float Arithmetic Mismatch Across Calls | `TypeError` | `TypeError` | No |
| `B005` | Invalid Literal in Transaction Segment Parsing | `ValueError` | `ValueError` | No |
| `B006` | Accidental Reset in Discount Accumulator Loop | `Logic error` | `LogicError (Incorrect Output)` | No |
| `B007` | Mutable Default Argument Permission Leak | `State/mutation bug` | `AssertionError` | No |
| `B008` | Incompatible None State in Order Cancellation | `Class/OOP bug` | `AttributeError` | **Yes** |
| `B009` | Case-Sensitive Lookup in Overridden Polymorphic Method | `Inheritance/polymorphism bug` | `KeyError` | **Yes** |
| `B010` | Multi-Frame Buffer Offset Boundary Overshoot | `Multi-function / deeper call-chain bug` | `IndexError` | No |

---

## 13. API / Backend Endpoints

The backend exposes the following REST endpoints and MCP service:

### Health Check
- `GET /health`: Returns service operational status.

### Code Execution
- `POST /execute`: Executes submitted code in sandbox or local fallback.
  - **Request Body**: `{"language": "python"|"java", "code": "...", "stdin": "..."}`
  - **Response**: `{"status": "success"|"runtime_error"|"timeout", "stdout": "...", "stderr": "...", "exit_code": 0, "execution_id": "...", "execution_time": 0.05}`

### Trace Inspection & Retrieval
- `GET /executions/{execution_id}`: Retrieves execution overview (status, duration, event count).
- `GET /executions/{execution_id}/error`: Retrieves the primary runtime exception event.
- `GET /executions/{execution_id}/stack`: Retrieves captured stack frames at point of failure.
- `GET /executions/{execution_id}/frames/{frame_id}/variables`: Retrieves local variables for a specific frame.
- `GET /executions/{execution_id}/source`: Retrieves source code lines around a location (`?file=...&line=...&radius=3`).
- `GET /executions/{execution_id}/path`: Retrieves bounded sequence of execution path events (`?max_events=100`).
- `GET /executions/{execution_id}/events/{event_id}`: Retrieves a specific runtime event by ID.
- `POST /executions/{execution_id}/search`: Searches execution trace events matching filter criteria.

### Debugging & Repair Agents
- `POST /debug/diagnose`: Invokes AI debugging agent to analyze runtime error.
  - **Request Body**: `{"execution_id": "...", "mode": "dynamic"|"baseline", "initial_context": "..."}`
  - **Response**: `DebugDiagnosis` (diagnosis, root_cause, evidence, suggested_fix, confidence, telemetry).
- `POST /debug/fix`: Runs the automated bug repair workflow.
  - **Request Body**: `{"execution_id": "...", "max_attempts": 3, "mode": "dynamic"|"baseline"}`
  - **Response**: `FixResult` (fixed_code, success, attempts, telemetry).

### M8 Evaluation
- `GET /evaluation/benchmarks`: Lists all 10 predefined benchmark cases.
- `GET /evaluation/benchmarks/{bug_id}`: Retrieves metadata for a specific benchmark.
- `POST /evaluation/run`: Runs a single evaluation experiment (Baseline or Dynamic).
- `POST /evaluation/run-paired`: Executes paired Baseline and Dynamic runs on a benchmark.
- `GET /evaluation/experiments`: Lists recent experiment history records (`?limit=30`).
- `GET /evaluation/experiments/{evaluation_id}/summary`: Retrieves paired comparison summary JSON.
- `GET /evaluation/experiments/{evaluation_id}/events`: Retrieves event timeline JSONL for an evaluation.
- `GET /evaluation/export/csv`: Downloads the complete evaluation dataset as a CSV file.

### Model Context Protocol (MCP) Server
- **Path**: Mounted at `/mcp` (Streamable HTTP transport)
- **Tools**:
  - `get_error_context`: Retrieve failing exception and error location.
  - `get_stack_trace`: Retrieve call stack frames without variable dumps.
  - `get_frame_variables`: Retrieve variables for a specific frame.
  - `get_source_context`: Retrieve window of source lines around a file/line.
  - `get_execution_path`: Retrieve bounded sequence of control flow events.
  - `get_event`: Retrieve a detailed event by event ID.
  - `search_trace`: Query trace events by event type, function, file, or line.

---

## 14. Troubleshooting

### 1. Backend Dependencies Installation Errors
- **Symptom**: `pip install -r requirements.txt` fails or throws compilation errors.
- **Solution**:
  - Verify Python version is 3.10 or higher (`python --version`).
  - Upgrade pip, setuptools, and wheel: `python -m pip install --upgrade pip setuptools wheel`.
  - Ensure you are working inside an activated virtual environment.

### 2. Docker Daemon Not Running
- **Symptom**: Warning in backend logs stating Docker connection failed.
- **Solution**:
  - Docker is **not strictly required**. The backend automatically falls back to local execution.
  - If you want container isolation, ensure Docker Desktop is running (`docker info`) and build the sandbox images (`docker build -t runtime-debugger-python backend/docker/python`).

### 3. Frontend Cannot Connect to Backend (Network Error)
- **Symptom**: Axios network errors or failed requests in the browser console.
- **Solution**:
  - Verify the backend is running on `http://localhost:8000` (`curl http://localhost:8000/health`).
  - Check `frontend/.env` to confirm `VITE_API_URL=http://localhost:8000`.
  - If modified, restart the Vite dev server (`Ctrl+C` then `npm run dev`).

### 4. CORS Errors in Browser Console
- **Symptom**: `Access to XMLHttpRequest ... blocked by CORS policy`.
- **Solution**:
  - Check `CORS_ORIGINS` in `backend/.env`. It must include `http://localhost:5173` and `http://127.0.0.1:5173`.
  - Restart the backend server after modifying `backend/.env`.

### 5. AI / LLM Provider Failures (Rate Limits or Missing Key)
- **Symptom**: The UI displays a friendly banner: *"AI service is currently unavailable. Please try again later."*
- **Solution**:
  - Verify that `OPENROUTER_API_KEY` is correctly set in `backend/.env`.
  - Check `backend/logs/app.log` for detailed diagnostic messages (such as rate limits or invalid authentication).
  - You can change the model via `LLM_MODEL` in `backend/.env` (e.g. `openrouter/free` or another supported model).

---

## 15. CI/CD

The project includes a minimal GitHub Actions continuous integration workflow configured in:
```text
.github/workflows/ci-cd.yml
```

Current workflow behavior:
- Triggers automatically on `push` events to the `main` branch.
- Runs on `ubuntu-latest`.
- Steps:
  1. Checks out the repository using `actions/checkout@v4`.
  2. Runs a baseline pipeline verification step.
  3. Outputs completion status.

*Note: Automated linting, test suites, and deployment stages are not currently part of the default CI pipeline and can be added as needed.*

---

## 16. Development Notes

- **Environment Files**: Always copy `.env.example` to `.env` for local configuration. Never commit `.env` containing sensitive credentials.
- **Benchmark vs. Experiment Data Separation**:
  - Benchmark task definitions are code specifications located in `backend/app/evaluation/benchmarks.py`.
  - Experiment records are generated runtime telemetry saved to `backend/data/m8/m8_experiments.csv`.
  - Loading or viewing benchmarks never modifies experiment data. Experiment records are only created upon explicit evaluation execution.
- **Running Backend Unit Tests**:
  ```bash
  cd backend
  # Run all evaluation tests
  python -m pytest tests/test_evaluation.py
  ```

---

## 17. Quick Start

### Quick Start with Docker Compose (Recommended)
Run the complete application in three commands:

```bash
# 1. Clone repository
git clone https://github.com/kamalesh2602/PW1.git
cd PW1

# 2. Configure environment (optional overrides)
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. Start everything with one command
docker compose up --build
```

Open `http://localhost:5173` in your browser.

---

### Alternative: Manual Local Startup
To run without Docker containers:

```bash
# 1. Start Backend (Terminal 1)
cd backend
python -m venv venv
# Linux/macOS: source venv/bin/activate | Windows PowerShell: .\venv\Scripts\Activate.ps1
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. Start Frontend (Terminal 2)
cd ../frontend
npm install
npm run dev
```

---

## 18. Logs and M8 Artifacts

The system produces several distinct log and artifact files during execution and evaluation. They serve different purposes and have different lifecycles:

| File / Path | Purpose | Generated By | Type | Safe to Reset? |
|:---|:---|:---|:---|:---:|
| `backend/data/m8/m8_experiments.csv` | **Master Tabular Dataset**: Main CSV recording all completed Baseline and Dynamic evaluation runs (Section 11 schema: 30 columns including tokens, times, context sizes, and success booleans). | `ExperimentLogger.log_experiment()` (`app/evaluation/logger.py`) | Final Research Dataset | **Yes** (resets dataset) |
| `backend/data/m8/m8_events.jsonl` | **Global Event Log**: Chronological line-delimited JSON stream of all evaluation lifecycle steps across all runs (e.g. `experiment_started`, `mcp_retrieval`, `curation_completed`, `fix_generated`). | `ExperimentLogger.log_event()` (`app/evaluation/logger.py`) | Raw Event Telemetry | **Yes** |
| `backend/data/m8/experiments/<eval_id>/summary.json` | **Pair Comparison Summary**: Side-by-side comparison artifact of a specific paired run (context reduction %, token reduction %, duration delta, status). | `ExperimentLogger.log_paired_summary()` (`app/evaluation/logger.py`) | Experiment Summary | **Yes** |
| `backend/data/m8/experiments/<eval_id>/baseline.json` | **Baseline Run Record**: Full dump of the Baseline `ExperimentRecord` for `<eval_id>`. | `ExperimentLogger.log_experiment()` (`app/evaluation/logger.py`) | Experiment Artifact | **Yes** |
| `backend/data/m8/experiments/<eval_id>/dynamic.json` | **Dynamic Run Record**: Full dump of the Dynamic `ExperimentRecord` for `<eval_id>`. | `ExperimentLogger.log_experiment()` (`app/evaluation/logger.py`) | Experiment Artifact | **Yes** |
| `backend/data/m8/experiments/<eval_id>/events.jsonl` | **Per-Run Event Log**: Scoped lifecycle events recorded specifically for `<eval_id>`. | `ExperimentLogger.log_event()` (`app/evaluation/logger.py`) | Per-Run Telemetry | **Yes** |
| `backend/data/m8_experiments.csv` | **Legacy Root CSV**: Maintained in `backend/data/` for backward compatibility with earlier evaluation test scripts. | Legacy runs / initial testing | Final Research Dataset | **Yes** |
| `backend/data/m8_events.jsonl` | **Legacy Root Events**: Maintained in `backend/data/` for backward compatibility. | Legacy runs / initial testing | Raw Event Telemetry | **Yes** |
| `backend/logs/app.log` | **Application Logs**: General operational log output for the backend, uvicorn server, route handlers, and agent debug logs. | `app.logging_config` loggers | Operational Log | **Yes** |
| `backend/app/evaluation/benchmarks.py` | **Benchmark Definitions**: Code definitions of B001 to B010. | Developer / Source Code | Source Code | **NO** (Preserve!) |

---

## 19. Tracing the Logging Flow

The following diagram illustrates how evaluation events and experiment artifacts are generated during an explicit evaluation run:

```text
User triggers evaluation (UI "Run Paired Evaluation" or POST /evaluation/run-paired)
   │
   ▼
EvaluationService.run_paired_experiment()  [app/evaluation/service.py]
   │
   ├── 1. Run Baseline Mode
   │      │
   │      ├── log_event("experiment_started", ...) ──► Appends to data/m8/m8_events.jsonl
   │      │                                         ──► Appends to .../experiments/<id>/events.jsonl
   │      ├── CodeExecutionService.execute_code()
   │      ├── DebuggingAgent.diagnose(mode="baseline")
   │      ├── FixerAgent.fix()
   │      ├── Validate semantic correctness
   │      └── log_experiment(record) ───────────────► Appends row to data/m8/m8_experiments.csv
   │                                                 ──► Overwrites .../experiments/<id>/baseline.json
   │                                                 ──► Writes .../experiments/<id>/summary.json
   │
   ├── 2. Run Dynamic Mode
   │      │
   │      ├── log_event("experiment_started", ...) ──► Appends to data/m8/m8_events.jsonl
   │      ├── ContextCurator.curate() (via MCP)   ──► Appends step events to events.jsonl
   │      ├── DebuggingAgent.diagnose(mode="dynamic")
   │      ├── FixerAgent.fix()
   │      ├── Validate semantic correctness
   │      └── log_experiment(record) ───────────────► Appends row to data/m8/m8_experiments.csv
   │                                                 ──► Overwrites .../experiments/<id>/dynamic.json
   │
   └── 3. Compute Comparison & Log Pair
          │
          ├── log_paired_summary(comparison) ───────► Overwrites .../experiments/<id>/summary.json
          └── log_event("evaluation_completed", ...) ──► Appends to events.jsonl
```

### When Each Artifact is Created
1. **At Step Start (`log_event`)**: As each phase starts (execution, MCP queries, LLM decisions, fix attempts), an entry is appended to `data/m8/m8_events.jsonl` and `<eval_id>/events.jsonl`.
2. **At Step Finish (`log_experiment`)**: When baseline or dynamic finishes, a new row is appended to `data/m8/m8_experiments.csv`, and `<eval_id>/baseline.json` or `dynamic.json` is written.
3. **At Evaluation Completion (`log_paired_summary`)**: The comparative analysis is saved to `<eval_id>/summary.json`.

---

## 20. Fresh Evaluation / Dataset Reset

There is intentionally **no "Reset Database" or "Clear Logs" button** in the UI to prevent accidental data loss during research evaluations.

If you need to start a completely fresh evaluation dataset:

### Step 1: Remove Generated Experiment Runs
Remove the individual per-run artifact folders:
```bash
# From the backend/ directory:
rm -rf data/m8/experiments/*
```
On Windows PowerShell:
```powershell
Remove-Item -Recurse -Force backend\data\m8\experiments\*
```

### Step 2: Reset the Master CSV and Events Log
Reset `m8_experiments.csv` to an empty file with only the header row, or remove it (the logger will automatically re-create the CSV with the correct headers on the next run):
```bash
# Linux/macOS:
rm -f data/m8/m8_experiments.csv data/m8/m8_events.jsonl
```
On Windows PowerShell:
```powershell
Remove-Item -Force backend\data\m8\m8_experiments.csv, backend\data\m8\m8_events.jsonl -ErrorAction SilentlyContinue
```

### Step 3: Clear General Application Logs (Optional)
```bash
# Linux/macOS:
rm -f logs/app.log
```
On Windows PowerShell:
```powershell
Remove-Item -Force backend\logs\app.log -ErrorAction SilentlyContinue
```

> **CRITICAL RULE**: 
> - **NEVER** delete or edit `backend/app/evaluation/benchmarks.py`. That file contains the immutable benchmark definitions.
> - Resetting experiment artifacts does **NOT** alter benchmark tasks or software behavior.

---

## 21. MCP Debugging

The project implements a Model Context Protocol (MCP) server adhering to the MCP specification for runtime trace inspection.

### Architecture & Modes

The MCP server can be run in two modes:

#### 1. Integrated Streamable HTTP Mode (Default / Application Mode)
- **Host / URL**: `http://localhost:8000/mcp`
- **Transport**: Streamable HTTP (`mcp.server.fastapi.streamable_http_app`)
- **How it runs**: Automatically mounted into FastAPI during application startup (`app/main.py`). When you start `uvicorn app.main:app`, the MCP endpoint is live.
- **Trace Sharing**: Directly shares the backend process's in-memory `TraceStore`. Any code executed via `POST /execute` or `EvaluationService` is immediately queryable via MCP tools without inter-process communication.

#### 2. Standalone Stdio Mode (CLI / External Agent Mode)
- **Entry Point**: `backend/app/mcp/server.py`
- **Transport**: Standard I/O (`stdio`)
- **Startup Command**:
  ```bash
  cd backend
  python -m app.mcp.server
  ```
- **Use Case**: Used when connecting external MCP clients (such as Claude Desktop or custom IDE extensions) via a subprocess pipe.

---

## 22. Important MCP & Debug REST Endpoints

While agents use MCP tools, developers can manually inspect traces and debug executions using these key REST endpoints. All trace queries require an `execution_id` returned from code execution.

### 1. Execute Code
- **`POST /execute`**
- **Purpose**: Runs code in sandbox and initializes a trace session.
- **Request Example**:
  ```json
  {
    "language": "python",
    "code": "def divide(a, b):\n    return a / b\nprint(divide(10, 0))"
  }
  ```
- **Response Key Field**: Returns `"execution_id": "0980a66a-679e-4c0a-9abb-2e444b5fe120"`.

### 2. Inspect Error Summary
- **`GET /executions/{execution_id}/error`**
- **Purpose**: Quickly see the failing line and exception without reading all events.
- **Response Example**:
  ```json
  {
    "event_id": 16,
    "error_type": "ZeroDivisionError",
    "message": "division by zero",
    "file": "script.py",
    "line": 2,
    "function": "divide"
  }
  ```

### 3. Inspect Call Stack
- **`GET /executions/{execution_id}/stack`**
- **Purpose**: Returns the call stack frames at the moment of failure.
- **Response Example**:
  ```json
  [
    {
      "frame_id": 0,
      "function": "divide",
      "file": "script.py",
      "line": 2
    },
    {
      "frame_id": 1,
      "function": "<module>",
      "file": "script.py",
      "line": 3
    }
  ]
  ```

### 4. Inspect Frame Local Variables
- **`GET /executions/{execution_id}/frames/{frame_id}/variables`**
- **Purpose**: Inspect local variable values inside a specific stack frame.
- **Response Example** (`frame_id=0`):
  ```json
  {
    "a": 10,
    "b": 0
  }
  ```

### 5. Inspect Source Window
- **`GET /executions/{execution_id}/source?file=script.py&line=2&radius=2`**
- **Purpose**: Retrieve source lines centered around the failure point.
- **Response Example**:
  ```json
  {
    "file": "script.py",
    "start_line": 1,
    "end_line": 3,
    "content": "1 | def divide(a, b):\n2 |     return a / b\n3 | print(divide(10, 0))"
  }
  ```

### 6. Inspect Execution Path
- **`GET /executions/{execution_id}/path?max_events=10`**
- **Purpose**: Get a concise chronological sequence of executed lines and function calls.

### 7. Search Trace Events
- **`POST /executions/{execution_id}/search`**
- **Purpose**: Filter trace events by event type, function, or exception.
- **Request Example**:
  ```json
  {
    "event_type": "exception",
    "max_results": 5
  }
  ```

---

## 23. Debugging Workflow

When investigating or diagnosing an execution failure manually, follow this standardized sequence:

```text
1. Execute code
   POST /execute ───────────────► Returns execution_id: "abc-123"
                                        │
2. Identify failure                     ▼
   GET /executions/abc-123/error ──► Finds error_type, line, and function
                                        │
3. Check call stack                     ▼
   GET /executions/abc-123/stack ──► Reveals caller frames (0, 1, 2, ...)
                                        │
4. Inspect runtime variables            ▼
   GET /executions/abc-123/frames/0/variables ──► Check values at point of crash
   GET /executions/abc-123/frames/1/variables ──► Check caller values
                                        │
5. Inspect source context               ▼
   GET /executions/abc-123/source?file=...&line=... ──► View offending code
                                        │
6. Diagnose or invoke agent             ▼
   POST /debug/diagnose ────────► AI Debugging Agent synthesizes diagnosis
   POST /debug/fix ─────────────► Fixer Agent generates and validates patch
```

`execution_id` is the primary key linking all execution traces, stack frames, variables, and debugging requests together.

---

## 24. MCP Tools Reference

The MCP server exposes seven specialized trace query tools. These allow the AI curator agent to fetch granular runtime context on demand without receiving the complete trace:

| MCP Tool Name | Purpose | Key Arguments |
|:---|:---|:---|
| `get_error_context` | Retrieves the primary runtime exception, failing function, file, and line. | `execution_id` |
| `get_stack_trace` | Retrieves the list of stack frames without bulk variable payloads. | `execution_id` |
| `get_frame_variables` | Retrieves local variable key-value pairs for a specific stack frame. | `execution_id`, `frame_id` |
| `get_source_context` | Retrieves a bounded slice of source lines around a file and line number. | `execution_id`, `file`, `line`, `radius` |
| `get_execution_path` | Retrieves a concise list of control-flow events (calls, returns, lines). | `execution_id`, `max_events` |
| `get_event` | Retrieves a single detailed event by ID, including its variables. | `execution_id`, `event_id` |
| `search_trace` | Searches events with filters (function, variable, exception type, line range). | `execution_id`, filters dict |

### REST vs. MCP
- **REST API (`/executions/*`)**: Human-facing endpoints used by the React frontend UI and developers testing with curl/Postman.
- **MCP Server (`/mcp`)**: Agent-facing protocol used by LLM agents (e.g. M7 Dynamic Context Curator) to iteratively explore runtime state via structured tool calls.

---

## 25. Practical Debugging Walkthrough

Here is a concrete example walking through benchmark **B001** (`Division by Zero in Function Call`):

### 1. Execute the Code
```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "def calculate(x):\n    return 10 / x\n\ndef process():\n    value = 0\n    return calculate(value)\n\nprocess()"
  }'
```

**Output**:
```json
{
  "status": "runtime_error",
  "language": "python",
  "stdout": "",
  "stderr": "ZeroDivisionError: division by zero",
  "exit_code": 1,
  "execution_id": "a93df24e-b5c6-48a0-9c1a-7b3d1f041234",
  "execution_time": 0.04
}
```

### 2. Query the Error Context
```bash
curl http://localhost:8000/executions/a93df24e-b5c6-48a0-9c1a-7b3d1f041234/error
```

**Output**:
```json
{
  "event_id": 16,
  "error_type": "ZeroDivisionError",
  "message": "division by zero",
  "file": "script.py",
  "line": 2,
  "function": "calculate"
}
```
*Observation: The failure is on line 2 in function `calculate()`.*

### 3. Query the Stack Trace
```bash
curl http://localhost:8000/executions/a93df24e-b5c6-48a0-9c1a-7b3d1f041234/stack
```

**Output**:
```json
[
  {
    "frame_id": 0,
    "function": "calculate",
    "file": "script.py",
    "line": 2
  },
  {
    "frame_id": 1,
    "function": "process",
    "file": "script.py",
    "line": 6
  },
  {
    "frame_id": 2,
    "function": "<module>",
    "file": "script.py",
    "line": 8
  }
]
```
*Observation: `calculate()` (frame 0) was invoked by `process()` (frame 1).*

### 4. Query Frame Variables
Inspect `calculate()` (frame 0):
```bash
curl http://localhost:8000/executions/a93df24e-b5c6-48a0-9c1a-7b3d1f041234/frames/0/variables
```
**Output**: `{"x": 0}` *(Argument `x` is 0).*

Inspect caller `process()` (frame 1):
```bash
curl http://localhost:8000/executions/a93df24e-b5c6-48a0-9c1a-7b3d1f041234/frames/1/variables
```
**Output**: `{"value": 0}` *(Caller initialized `value = 0`).*

### 5. Root Cause Conclusion
The caller `process()` initializes `value = 0` and passes it to `calculate(x)`, where it evaluates as the divisor in `10 / x` without validation. The fix requires passing a non-zero divisor or adding a zero check inside `calculate()`.
