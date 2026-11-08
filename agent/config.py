"""Configuration : lit le fichier .env et définit les chemins."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# utf-8-sig : accepte un .env enregistré "UTF-8 avec BOM" (piège classique sous Windows)
load_dotenv(ROOT / ".env", encoding="utf-8-sig")

TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_DB_ID", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

STATE_FILE = ROOT / "state.json"
LOG_DIR = ROOT / "logs"