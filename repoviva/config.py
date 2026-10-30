from pathlib import Path
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")

DB_PATH = Path(os.getenv("REPOVIVA_DB_PATH", str(DATA_DIR / "repoviva.db"))).expanduser()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_API_VERSION = "2026-03-10"
MAX_README_CHARS = 20_000
MAX_REPOSITORIES = 200
