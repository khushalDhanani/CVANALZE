# CV Analyzer

A FastAPI-based application for analyzing CVs/resumes, matching them against job descriptions, and providing scoring and insights.

## Supported CV uploads

Both `/api/cv/upload` and `/api/match/upload` accept PDF and DOCX files only.
Legacy `.doc` and plain-text `.txt` uploads are intentionally unsupported.
Uploads are size-bounded, checked against their declared MIME type and file signature, structurally validated, and persisted under server-generated names before background processing begins.
See `backend/docs/phase1-secure-uploads.md` for limits, retention, and reprocessing behavior.
See `backend/docs/phase2-identity-and-caching.md` for canonical CV identity, collision handling, and cache isolation.
See `backend/docs/phase3-structured-cv-processing.md` for normalized resume contracts, experience authority, and reusable analysis contexts.
See `backend/docs/phase4-reliable-background-processing.md` for persisted Redis/RQ jobs, retry states, distributed locking, polling compatibility, and the development fallback.

## Project Structure

```
cv-analyzer/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── cv.py
│   │   ├── jobs.py
│   │   └── analysis.py
│   ├── schemas/
│   │   ├── resume.py
│   │   ├── job.py
│   │   └── analysis.py
│   ├── services/
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   ├── ocr_service.py
│   │   ├── cv_parser.py
│   │   ├── llm_service.py
│   │   ├── skill_normalizer.py
│   │   └── scoring_engine.py
│   ├── models/
│   ├── repositories/
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   └── prompts/
├── uploads/
├── tests/
├── scripts/
├── .env
├── requirements.txt
└── README.md
```

## Getting Started

1. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run FastAPI application:
   ```bash
   uvicorn app.main:app --reload
   ```
