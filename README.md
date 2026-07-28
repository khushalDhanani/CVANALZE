# CV Analyzer

A FastAPI-based application for analyzing CVs/resumes, matching them against job descriptions, and providing scoring and insights.

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
