from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Direction(str, Enum):
    DE_EN = "de-en"
    EN_DE = "en-de"


class JobStatus(str, Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    TRANSLATING = "TRANSLATING"
    RENDERING = "RENDERING"
    DONE = "DONE"
    FAILED = "FAILED"


class UploadResponse(BaseModel):
    job_id: str


class TranslateResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0
    message: str = ""
    error: Optional[str] = None


class TextBlock(BaseModel):
    id: str
    bbox: list[float]
    text: str
    font_size: float = 11.0
    is_bold: bool = False
    is_italic: bool = False
    color: list[float] = [0.0, 0.0, 0.0]  # RGB, values 0–1


class PageData(BaseModel):
    page_number: int
    width: float
    height: float
    blocks: list[TextBlock]


class TranslationSegment(BaseModel):
    id: str
    text: str
