"""Apply schema. Idempotent."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, SCHEMA_PATH


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    conn = connect()
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"[ok] schema applied → {DB_PATH}")


if __name__ == "__main__":
    init()
