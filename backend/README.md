# PW1 - Backend Service

FastAPI execution engine for Python and Java code running inside isolated Docker containers.

## Features
- `POST /execute` endpoint accepting code payload for Python or Java.
- Docker-based sandboxed execution (memory limit, CPU limits, no network access).
- Structured JSON response (`status`, `stdout`, `stderr`, `exit_code`, `execution_time`).

## Quick Start

### 1. Install Dependencies
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Build Docker Executor Images
```bash
docker build -t runtime-debugger-python ./docker/python
docker build -t runtime-debugger-java ./docker/java
```

### 3. Run FastAPI Server
```bash
uvicorn app.main:app --reload --port 8000
```
