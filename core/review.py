"""Scan-scoped false-positive review. Original encrypted scan reports are never rewritten."""
from __future__ import annotations

import hashlib
from core import audit
from core.db import connect, decrypt, encrypt
from core.schemas import Report


def _owned_scan(c, user_id: int, scan_id: int):
    row = c.execute(
        "SELECT s.* FROM scans s JOIN engagements e ON e.id=s.engagement_id "
        "JOIN users u ON u.client_id=e.client_id WHERE s.id=? AND u.id=? AND u.role='client'",
        (scan_id, user_id)).fetchone()
    if not row:
        raise PermissionError("Scan does not belong to this client")
    return row


def dismiss(user_id: int, scan_id: int, finding_id: str, reason: str) -> None:
    reason = reason.strip()
    if not 5 <= len(reason) <= 2000:
        raise ValueError("Give a reason between 5 and 2000 characters")
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        scan = _owned_scan(c, user_id, scan_id)
        report = Report.model_validate_json(decrypt(scan["report_enc"]))
        if finding_id not in {f.id for f in report.findings if f.source != "profile"}:
            raise ValueError("Only a detected finding from this scan can be dismissed")
        c.execute("INSERT INTO finding_dismissals (scan_id,finding_id,reason_enc,user_id) VALUES (?,?,?,?) "
                  "ON CONFLICT(scan_id,finding_id) DO UPDATE SET reason_enc=excluded.reason_enc, "
                  "user_id=excluded.user_id, created_at=datetime('now')",
                  (scan_id, finding_id, encrypt(reason), user_id))
        audit.append(c, "finding_dismissed", user_id, scan["target"], scan["engagement_id"], details={
            "scan_id": scan_id, "finding_id": finding_id,
            "reason_sha256": hashlib.sha256(reason.encode()).hexdigest()})


def restore(user_id: int, scan_id: int, finding_id: str) -> None:
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        scan = _owned_scan(c, user_id, scan_id)
        count = c.execute("DELETE FROM finding_dismissals WHERE scan_id=? AND finding_id=?",
                          (scan_id, finding_id)).rowcount
        if count:
            audit.append(c, "finding_restored", user_id, scan["target"], scan["engagement_id"],
                         details={"scan_id": scan_id, "finding_id": finding_id})


def dismissals(user_id: int, scan_id: int) -> list[dict]:
    with connect() as c:
        _owned_scan(c, user_id, scan_id)
        return [{"finding_id": r["finding_id"], "reason": decrypt(r["reason_enc"]),
                 "user_id": r["user_id"], "created_at": r["created_at"]}
                for r in c.execute("SELECT * FROM finding_dismissals WHERE scan_id=? ORDER BY finding_id", (scan_id,))]
