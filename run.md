# CV Analyzer - How to Run

This document outlines the steps required to run the CV Analyzer pipeline using either **Docker Compose (Containerized)** or **Local Development Services (FastAPI, RQ Worker, Expo)**.

---

## 1. Prerequisites & Environment Setup

Ensure your `.env` file is present in the project root directory (and/or `backend/`). It should contain:

```ini
POSTGRES_APP_URL=postgresql://postgres:postgres@localhost:5432/cv_analyzer
MSSQL_READ_ONLY_URL=mssql+pyodbc://sa:your_password@172.25.1.160:1433/AIRIS_TEST?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
REDIS_URL=redis://localhost:6379/0
```

> **macOS Note**: Due to `PyTorch` (used by `docling`) fork-safety issues on macOS when running locally outside Docker, you **MUST** prefix commands that spawn workers or run ML models with `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`.

---

## 2. Running via Docker Compose (Recommended)

Docker Compose manages the full stack including `pgvector`, `redis`, `api`, and `worker` with MS ODBC SQL drivers pre-installed.

### A. Start Full Stack
```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

### B. Updating Docker Containers After Backend Code Changes
Because backend source code is compiled into the container image, run `--build` whenever backend `.py` files are modified:

```bash
# Rebuild & restart backend API and Worker containers:
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build api worker

# Or rebuild the entire stack:
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

### C. Container Logs & Status
```bash
# View live logs for API and Worker:
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f api worker

# Stop all containers:
docker compose -f docker-compose.yml -f docker-compose.local.yml down
```

---

## 3. Running Locally (Without Docker)

Before starting local services, ensure Redis and Ollama are running on your host machine:

- **Redis Server**:
  ```bash
  brew services start redis
  redis-cli ping   # Expected output: PONG
  ```

- **Ollama**:
  ```bash
  ollama serve
  ```

### A. Start the RQ Worker (Background Processing)
The background worker processes heavy CV extraction and LLM matching tasks. On an Apple Silicon Mac, run exactly one worker:

```bash
cd backend
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python start_worker.py
```

### B. Start the FastAPI Server (Web API & WebSockets)
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

*(If port 8000 is busy: `kill -9 $(lsof -t -i:8000)`)*  
*(Interactive OpenAPI Docs: http://localhost:8000/docs)*  
*(Cache Analytics: http://localhost:8000/api/analytics/cache)*

### C. Run the CLI Batch Processor (Testing)
```bash
cd backend
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python main.py
```

---

## 4. Testing WebSockets (Optional)

To verify real-time PubSub progress event broadcasting:

```bash
cd backend
uv run python test_ws.py
```

---

## 5. Starting the Frontend (React Native / Expo)

The UI code is located in the `frontend/` directory.

To start the Expo development server:

```bash
cd frontend
npm start
```

Press `w` to open in a web browser, `i` for iOS Simulator, or `a` for Android.
