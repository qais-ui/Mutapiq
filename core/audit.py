"""Append-only, hash-chained audit log.

Each row stores sha256(prev_hash + canonical JSON of the row). Editing or deleting any
past row breaks every hash after it, and verify_chain() reports the first broken row.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3

from core.db import connect

GENESIS = "0" * 64


def _digest(prev_hash: str, row: dict) -> str:
    canonical = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def log(action: str, user_id: int | None = None, target: str | None = None,
        engagement_id: str | None = None, allowed: bool | None = None, details: dict | None = None) -> str:
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        return append(c, action, user_id, target, engagement_id, allowed, details)


def append(c: sqlite3.Connection, action: str, user_id: int | None = None, target: str | None = None,
           engagement_id: str | None = None, allowed: bool | None = None, details: dict | None = None) -> str:
    """Append inside the caller's write transaction so data changes and audit events commit together."""
    if not c.in_transaction:
        raise ValueError("An active write transaction is required")
    last = c.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev = last["hash"] if last else GENESIS
    row = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "user_id": user_id,
           "action": action, "target": target, "engagement_id": engagement_id,
           "allowed": None if allowed is None else int(allowed),
           "details": json.dumps(details or {}, sort_keys=True, ensure_ascii=False)}
    h = _digest(prev, row)
    c.execute("INSERT INTO audit_log (ts,user_id,action,target,engagement_id,allowed,details,prev_hash,hash) "
              "VALUES (:ts,:user_id,:action,:target,:engagement_id,:allowed,:details,:prev,:hash)",
              {**row, "prev": prev, "hash": h})
    return h


def entries(limit: int = 200, engagement_id: str | None = None) -> list[dict]:
    with connect() as c:
        if engagement_id:
            rows = c.execute("SELECT * FROM audit_log WHERE engagement_id=? ORDER BY id DESC LIMIT ?", (engagement_id, limit))
        else:
            rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def export_for_client(user_id: int, engagement_id: str | None = None) -> str:
    """Complete company-scoped export, including ended contracts; never export the global log."""
    with connect() as c:
        user = c.execute("SELECT role, client_id FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or user["role"] != "client" or user["client_id"] is None:
            raise PermissionError("A client login is required")
        if engagement_id is not None and not c.execute(
                "SELECT 1 FROM engagements WHERE id=? AND client_id=?",
                (engagement_id, user["client_id"])).fetchone():
            raise PermissionError("Engagement does not belong to this client")
        rows = c.execute(
            "SELECT a.* FROM audit_log a JOIN engagements e ON e.id=a.engagement_id "
            "WHERE e.client_id=? AND (? IS NULL OR e.id=?) ORDER BY a.id",
            (user["client_id"], engagement_id, engagement_id))
        # Global chain hashes are omitted: a company subset is not a standalone verifiable chain.
        fields = ("id", "ts", "action", "target", "engagement_id", "allowed", "details")
        records = [{k: r[k] for k in fields} for r in rows]
    return json.dumps({"format": "mutabiq-client-audit-v1", "entries": records,
                       "note": "Company-scoped export; global chain verification is available to admins."},
                      ensure_ascii=False, indent=2)


def verify_chain() -> dict:
    prev = GENESIS
    with connect() as c:
        for r in c.execute("SELECT * FROM audit_log ORDER BY id"):
            row = {k: r[k] for k in ("ts", "user_id", "action", "target", "engagement_id", "allowed", "details")}
            if r["prev_hash"] != prev or _digest(prev, row) != r["hash"]:
                return {"ok": False, "broken_at_id": r["id"]}
            prev = r["hash"]
    return {"ok": True, "head": prev}
