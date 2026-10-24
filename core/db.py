"""SQLite connection + at-rest encryption helpers."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("MUTABIQ_DB", ROOT / "db" / "mutabiq.db"))
KEY_PATH = ROOT / "db" / ".fernet.key"     # never commit (in .gitignore)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript((ROOT / "db" / "schema.sql").read_text())


def _fernet() -> Fernet:
    key = os.environ.get("MUTABIQ_KEY")
    if not key:
        if not KEY_PATH.exists():
            KEY_PATH.write_bytes(Fernet.generate_key())
        key = KEY_PATH.read_bytes()
    return Fernet(key)


def encrypt(text: str) -> bytes:
    return _fernet().encrypt(text.encode())


def decrypt(blob: bytes) -> str:
    return _fernet().decrypt(blob).decode()
