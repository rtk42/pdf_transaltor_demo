import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env from cwd (backend/) or parent directories

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_FILE_MB: int = int(os.getenv("MAX_FILE_MB", "20"))
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "50"))
JOB_TTL_MINUTES: int = int(os.getenv("JOB_TTL_MINUTES", "60"))
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)
