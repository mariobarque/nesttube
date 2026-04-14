import os
from pathlib import Path
from dotenv import load_dotenv

# BASE_DIR is the project root (parent of this shared/ package)
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
ADMIN_PASSCODE_HASH: str = os.getenv("ADMIN_PASSCODE_HASH", "")
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
PORT: int = int(os.getenv("PORT", "8000"))

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'nesttube.db'}"
