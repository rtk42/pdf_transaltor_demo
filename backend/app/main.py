"""FastAPI application – PDF Translator backend."""

from __future__ import annotations

import logging
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import config
from .jobs import create_job, get_job, run_pipeline, start_cleanup_thread
from .schemas import Direction, JobStatus, StatusResponse, TranslateResponse, UploadResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF Translator", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    start_cleanup_thread()
    logger.info("PDF Translator backend started. DATA_DIR=%s", config.DATA_DIR)


# ── Upload ───────────────────────────────────────────────────────────────

@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile, direction: str = "de-en") -> UploadResponse:
    # Validate content type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Validate direction
    try:
        dir_enum = Direction(direction)
    except ValueError:
        raise HTTPException(status_code=400, detail="direction must be 'de-en' or 'en-de'.")

    # Read file and check size
    data = await file.read()
    max_bytes = config.MAX_FILE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File exceeds {config.MAX_FILE_MB} MB limit.")

    # Check page count (quick open)
    import fitz

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        page_count = len(doc)
        doc.close()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read PDF file.")

    if page_count > config.MAX_PAGES:
        raise HTTPException(status_code=400, detail=f"PDF has {page_count} pages; max is {config.MAX_PAGES}.")

    # Create job and persist input
    job = create_job(dir_enum)
    job.input_pdf.write_bytes(data)

    logger.info("Uploaded job %s (%d pages, direction=%s)", job.job_id, page_count, direction)
    return UploadResponse(job_id=job.job_id)


# ── Translate ────────────────────────────────────────────────────────────

@app.post("/api/translate/{job_id}", response_model=TranslateResponse)
async def translate(job_id: str, background_tasks: BackgroundTasks) -> TranslateResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status not in (JobStatus.UPLOADED, JobStatus.FAILED):
        raise HTTPException(status_code=409, detail=f"Job is already {job.status.value}.")

    # Run pipeline in a background thread so it doesn't block the event loop.
    def _run() -> None:
        run_pipeline(job)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return TranslateResponse(job_id=job.job_id, status="STARTED")


# ── Status ───────────────────────────────────────────────────────────────

@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def status(job_id: str) -> StatusResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return StatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        error=job.error,
    )


# ── Result ───────────────────────────────────────────────────────────────

@app.get("/api/result/{job_id}")
async def result(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=409, detail="Translation is not done yet.")
    if not job.output_pdf.exists():
        raise HTTPException(status_code=500, detail="Output file missing.")

    return FileResponse(
        path=str(job.output_pdf),
        media_type="application/pdf",
        filename=f"translated_{job.job_id}.pdf",
    )
