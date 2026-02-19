# PDF Translator (DE ⇄ EN)

A web application that translates PDF documents between German and English.
Uses **FastAPI** for the backend API, **Streamlit** for the frontend UI,
**PyMuPDF** for PDF parsing, **ReportLab** for PDF reconstruction, and
the **OpenAI API** for translation.

## Features

- Upload any text-based PDF (up to 20 MB / 50 pages by default)
- Translate German → English or English → German
- Progress tracking through the pipeline (extract → translate → render)
- Download the translated PDF with preserved page count and layout
- Automatic cleanup of expired job data

## Project Structure

```
backend/
  app/
    main.py          # FastAPI endpoints
    config.py        # Environment-based configuration
    schemas.py       # Pydantic models and enums
    jobs.py          # Job store and translation pipeline
    pdf_extract.py   # PyMuPDF text extraction
    translate.py     # OpenAI translation with chunking + retries
    pdf_render.py    # ReportLab PDF reconstruction
    utils.py         # Misc helpers
  requirements.txt
frontend/
  streamlit_app.py   # Streamlit UI
  requirements.txt
.env.example         # Environment variable template
```

## Prerequisites

- Python 3.11+
- An OpenAI API key

## Setup

1. Copy `.env.example` to `.env` and fill in your `OPENAI_API_KEY`.

2. **Backend**:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

3. **Frontend** (in a separate terminal):

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The Streamlit UI defaults to `http://localhost:8501` and connects to the
backend at `http://localhost:8000`. Set the `BACKEND_URL` environment
variable to change the backend address.

## API Endpoints

| Method | Path                      | Description                |
|--------|---------------------------|----------------------------|
| POST   | `/api/upload`             | Upload PDF + set direction |
| POST   | `/api/translate/{job_id}` | Start translation pipeline |
| GET    | `/api/status/{job_id}`    | Poll job progress          |
| GET    | `/api/result/{job_id}`    | Download translated PDF    |

## Configuration (Environment Variables)

| Variable          | Default       | Description                    |
|-------------------|---------------|--------------------------------|
| `OPENAI_API_KEY`  | *(required)*  | OpenAI API key                 |
| `OPENAI_MODEL`    | `gpt-4o-mini` | Model for translation          |
| `MAX_FILE_MB`     | `20`          | Max upload size in MB          |
| `MAX_PAGES`       | `50`          | Max page count per PDF         |
| `JOB_TTL_MINUTES` | `60`          | Minutes before job cleanup     |
| `DATA_DIR`        | `./data`      | Directory for temporary files  |
| `BACKEND_URL`     | `http://localhost:8000` | (Frontend only) Backend URL |
