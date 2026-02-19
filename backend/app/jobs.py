"""In-memory job store and translation pipeline."""

from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config
from .pdf_extract import extract_pages, total_text_length
from .pdf_render import render_pdf
from .schemas import Direction, JobStatus, TranslationSegment

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 50  # below this we assume scanned / image-only PDF


@dataclass
class Job:
    job_id: str
    direction: Direction
    status: JobStatus = JobStatus.UPLOADED
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @property
    def folder(self) -> Path:
        return config.DATA_DIR / self.job_id

    @property
    def input_pdf(self) -> Path:
        return self.folder / "input.pdf"

    @property
    def output_pdf(self) -> Path:
        return self.folder / "output.pdf"


# Thread-safe in-memory store
_lock = threading.Lock()
_jobs: dict[str, Job] = {}


def create_job(direction: Direction) -> Job:
    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id=job_id, direction=direction)
    job.folder.mkdir(parents=True, exist_ok=True)
    with _lock:
        _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


def _update(job: Job, **kwargs: object) -> None:
    with _lock:
        for k, v in kwargs.items():
            setattr(job, k, v)


def run_pipeline(job: Job) -> None:
    """Execute the full extract → translate → render pipeline."""
    try:
        # --- Extract ---
        _update(job, status=JobStatus.EXTRACTING, progress=10, message="Extracting text from PDF")
        pages = extract_pages(str(job.input_pdf))

        char_count = total_text_length(pages)
        if char_count < MIN_TEXT_CHARS:
            _update(
                job,
                status=JobStatus.FAILED,
                error="The PDF appears to be scanned or image-only. Text extraction found very little content.",
            )
            return

        _update(job, progress=25, message="Extraction complete")

        # --- Translate ---
        _update(job, status=JobStatus.TRANSLATING, progress=30, message="Translating text")

        all_segments = [
            TranslationSegment(id=b.id, text=b.text)
            for p in pages
            for b in p.blocks
        ]

        def on_progress(done: int, total: int) -> None:
            pct = 30 + int(50 * done / max(total, 1))
            _update(job, progress=pct, message=f"Translated chunk {done}/{total}")

        translations = _translate_with_api(all_segments, job.direction, on_progress)

        _update(job, progress=80, message="Translation complete")

        # --- Render ---
        _update(job, status=JobStatus.RENDERING, progress=85, message="Rebuilding PDF")
        render_pdf(pages, translations, str(job.output_pdf))

        _update(job, status=JobStatus.DONE, progress=100, message="Translation complete")

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job.job_id)
        _update(job, status=JobStatus.FAILED, error=str(exc))


def _translate_with_api(
    segments: list[TranslationSegment],
    direction: Direction,
    on_progress: object,
) -> dict[str, str]:
    from .translate import translate_segments

    return translate_segments(segments, direction, on_progress=on_progress)  # type: ignore[arg-type]


# --- Cleanup ---

def cleanup_expired_jobs() -> None:
    """Remove jobs older than JOB_TTL_MINUTES."""
    now = time.time()
    ttl_seconds = config.JOB_TTL_MINUTES * 60
    with _lock:
        expired = [jid for jid, j in _jobs.items() if now - j.created_at > ttl_seconds]
        for jid in expired:
            job = _jobs.pop(jid, None)
            if job and job.folder.exists():
                shutil.rmtree(job.folder, ignore_errors=True)
            logger.info("Cleaned up expired job %s", jid)


def start_cleanup_thread() -> None:
    """Run periodic cleanup in a daemon thread."""

    def _loop() -> None:
        while True:
            time.sleep(300)  # every 5 minutes
            try:
                cleanup_expired_jobs()
            except Exception:
                logger.exception("Cleanup error")

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
