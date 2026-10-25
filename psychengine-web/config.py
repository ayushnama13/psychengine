"""Central config. Loads .env.api_keys + .env if present."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path("/home/ayush/projects")
PKG_ROOT = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env.api_keys")
load_dotenv(PKG_ROOT / ".env", override=False)

DB_PATH = Path(os.getenv("PSYCH_DB", PKG_ROOT / "db" / "psych.db"))
BOOKS_DIR = Path(os.getenv("PSYCH_BOOKS_DIR", PROJECT_ROOT / "books"))
SCHEMA_PATH = PKG_ROOT / "db" / "schema.sql"

def cerebras_keys():
    keys = [os.getenv(f"CEREBRAS_API_KEY_{i}") for i in range(1, 10)]
    keys = [k for k in keys if k]
    default = os.getenv("CEREBRAS_API_KEY")
    if default and default not in keys:
        keys.insert(0, default)
    return keys

def groq_keys():
    keys = [os.getenv(f"GROQ_API_KEY_{i}") for i in range(1, 12)]
    keys = [k for k in keys if k]
    default = os.getenv("GROQ_API_KEY")
    if default and default not in keys:
        keys.insert(0, default)
    return keys

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DEFAULT_CHUNK_TOKENS = 1000
SESSION_DEFAULT_MINUTES = 45
NEW_TOPIC_INTERVAL_DAYS = 3
LAYER_INTERVALS = {1: 0, 2: 3, 3: 7, 4: 30, 5: 90}
