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

Before starting local services, ensure PostgreSQL (pgvector), Redis, and Ollama are running on your host machine:

- **PostgreSQL (`pgvector`) Server**:
  ```bash
  docker compose up -d pgvector
  ```

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

---

## 6. Fresh Reset / Clean Start

To test the system from a completely fresh start without deleting database schemas, master data (departments, designations, vacancies, taxonomy), or system configuration:

### Quick Single-Command Reset
```bash
cd backend
uv run python scripts/reset_runtime_data.py
```

---

### Step-by-Step Reset Workflow

#### Step 1: Stop Services & Workers
Stop any active background workers, FastAPI backend server, and frontend dev server:
```bash
# Stop FastAPI backend server (port 8000)
kill -9 $(lsof -t -i:8000) 2>/dev/null || true

# Stop RQ background worker
pkill -f "start_worker.py" 2>/dev/null || true

# Stop Expo frontend dev server (port 8081)
kill -9 $(lsof -t -i:8081) 2>/dev/null || true
```

#### Step 2: Clear Generated Database / Cache / Job Data
> **WARNING**: The following commands purge generated runtime state (candidate analysis, background job queues, disk caches). They **DO NOT** remove database schema, master taxonomy, departments, designations, vacancies, domain embeddings, or configuration.

1. **Run Pending Database Migrations**:
```bash
cd backend
uv run python scripts/run_migrations.py
```

2. **Truncate PostgreSQL Generated Tables & Flush Embedding Cache**:
```bash
cd backend
uv run python -c "
from app.core.database import postgres_app_engine
from app.core.cache import embedding_cache_manager
from sqlalchemy import text
tables = [
    'public.cv_results', 'public.candidate_embeddings', 'public.department_alias_mappings',
    'cvai.candidates', 'cvai.cv_documents', 'cvai.cv_results', 'cvai.match_results', 'cvai.match_results_history',
    'integration.sync_runs', 'integration.sync_errors', 'integration.sync_watermarks', 'integration.candidate_snapshots',
    'validation.shadow_validation_runs', 'validation.shadow_validation_results', 'validation.validation_metrics_snapshots', 'validation.hr_disagreement_reviews'
]
with postgres_app_engine.connect() as conn:
    for t in tables:
        try:
            conn.execute(text(f'TRUNCATE TABLE {t} CASCADE;'))
        except Exception:
            pass
    conn.commit()
embedding_cache_manager.clear()
print('PostgreSQL generated tables and embedding_cache_manager L2/L3 cache cleared.')
"
```

3. **Flush Redis Cache & RQ Queues**:
```bash
redis-cli flushdb
```

4. **Clear Local Disk Caches & Upload Artifacts**:
```bash
rm -f backend/llm_cache.db
rm -rf uploads/.doc_cache/* uploads/.embed_cache/* uploads/.llm_cache/* uploads/.processing_jobs/* uploads/.locks/* uploads/results/* uploads/*.pdf uploads/*.docx uploads/*.doc 2>/dev/null || true
rm -rf backend/uploads/.doc_cache/* backend/uploads/.embed_cache/* backend/uploads/.llm_cache/* backend/uploads/.processing_jobs/* backend/uploads/.locks/* backend/uploads/results/* backend/uploads/*.pdf backend/uploads/*.docx backend/uploads/*.doc 2>/dev/null || true
```

#### Step 3: Restart Services
```bash
# 1. Ensure Redis is active:
brew services restart redis

# 2. Start RQ Worker (Terminal 1):
cd backend
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python start_worker.py

# 3. Start FastAPI Server (Terminal 2):
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start Frontend (Terminal 3):
cd frontend
npm start
```

#### Step 4: Verify DB/Cache & Embedding Table Schema is Clean
```bash
cd backend
uv run python -c "
from app.core.database import postgres_app_engine
from app.core.cache import embedding_cache_manager
from sqlalchemy import inspect, text

inspector = inspect(postgres_app_engine)
cand_cols = {c['name'] for c in inspector.get_columns('candidate_embeddings')}
vac_cols = {c['name'] for c in inspector.get_columns('vacancy_embeddings')}
req = {'source_snapshot', 'source_watermark', 'freshness_status'}

assert req.issubset(cand_cols), f'candidate_embeddings missing: {req - cand_cols}'
assert req.issubset(vac_cols), f'vacancy_embeddings missing: {req - vac_cols}'

with postgres_app_engine.connect() as conn:
    cv_res = conn.execute(text('SELECT COUNT(*) FROM public.cv_results')).scalar()
    cand_emb = conn.execute(text('SELECT COUNT(*) FROM public.candidate_embeddings')).scalar()
    dept_dom = conn.execute(text('SELECT COUNT(*) FROM \"DepartmentDomainMaster\"')).scalar()
    print(f'Verification: cv_results={cv_res} (expect 0), candidate_embeddings={cand_emb} (expect 0), DepartmentDomainMaster={dept_dom} (expect >0)')
    print('Schema Check: Both candidate_embeddings and vacancy_embeddings contain source_snapshot, source_watermark, freshness_status columns.')
"

redis-cli keys "*"
```

#### Step 5: Process a CV from Scratch
```bash
# Option A: Upload a PDF file via API:
curl -X POST "http://localhost:8000/api/cv/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/sample_resume.pdf"

# Option B: Run batch processor over uploads/ directory:
cd backend
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python main.py
```


