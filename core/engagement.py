"""Contract (engagement) registry. The contract itself is signed OUTSIDE the app;
a Mutabiq admin records it here after checking the signed letter and commercial registration."""
from __future__ import annotations

import datetime as dt
import secrets

import bcrypt

from core import audit
from core.db import connect
from core.scanner import normalize_target


def create_client(legal_name: str, commercial_reg: str, contact_email: str = "") -> int:
    with connect() as c:
        cur = c.execute("INSERT INTO clients (legal_name, commercial_reg, contact_email) VALUES (?,?,?)",
                        (legal_name, commercial_reg, contact_email))
        return cur.lastrowid


def create_user(username: str, password: str, role: str, client_id: int | None = None, display_name: str = "") -> int:
    pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with connect() as c:
        cur = c.execute("INSERT INTO users (username,password_hash,display_name,role,client_id) VALUES (?,?,?,?,?)",
                        (username, pw, display_name or username, role, client_id))
        return cur.lastrowid


def check_login(username: str, password: str) -> dict | None:
    with connect() as c:
        u = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if u and bcrypt.checkpw(password.encode(), u["password_hash"].encode()):
        return dict(u)
    return None


def create_engagement(eng_id: str, client_id: int, domains: list[str], valid_from: str, valid_to: str,
                      signatory_name: str, signatory_title: str, allowed_scans=("passive_web", "infra_map"),
                      contract_file: str | None = None, admin_id: int | None = None) -> dict:
    token = f"mutabiq-verify={eng_id}-{secrets.token_hex(4)}"
    with connect() as c:
        c.execute("INSERT INTO engagements (id,client_id,valid_from,valid_to,allowed_scans,signatory_name,"
                  "signatory_title,contract_file,verify_token) VALUES (?,?,?,?,?,?,?,?,?)",
                  (eng_id, client_id, valid_from, valid_to, ",".join(allowed_scans), signatory_name,
                   signatory_title, contract_file, token))
        for d in domains:
            c.execute("INSERT INTO scope_targets (engagement_id, domain) VALUES (?,?)", (eng_id, normalize_target(d)))
    audit.log("engagement_created", admin_id, ",".join(domains), eng_id, True,
              {"valid_from": valid_from, "valid_to": valid_to, "signatory": signatory_name})
    return get_engagement(eng_id)


def get_engagement(eng_id: str) -> dict | None:
    with connect() as c:
        e = c.execute("SELECT e.*, cl.legal_name FROM engagements e JOIN clients cl ON cl.id=e.client_id WHERE e.id=?",
                      (eng_id,)).fetchone()
        if not e:
            return None
        scope = [r["domain"] for r in c.execute("SELECT domain FROM scope_targets WHERE engagement_id=?", (eng_id,))]
    d = dict(e)
    d["scope"] = scope
    d["allowed_scans"] = d["allowed_scans"].split(",")
    return d


def active_engagements_for_client(client_id: int) -> list[dict]:
    today = dt.date.today().isoformat()
    with connect() as c:
        ids = [r["id"] for r in c.execute(
            "SELECT id FROM engagements WHERE client_id=? AND status='active' AND valid_from<=? AND valid_to>=?",
            (client_id, today, today))]
    return [get_engagement(i) for i in ids]


def list_engagements() -> list[dict]:
    with connect() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM engagements ORDER BY created_at DESC")]
    return [get_engagement(i) for i in ids]


def set_status(eng_id: str, status: str, admin_id: int | None = None) -> None:
    if status not in ("revoked", "expired"):
        raise ValueError("Only revocation or expiry is supported; record a new contract to renew")
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        if not c.execute("SELECT 1 FROM engagements WHERE id=?", (eng_id,)).fetchone():
            raise ValueError("Unknown engagement")
        c.execute("UPDATE engagements SET status=? WHERE id=?", (status, eng_id))
        audit.append(c, f"engagement_{status}", admin_id, None, eng_id, True)


def expire_old() -> int:
    """Run on app start: contracts past their end date become 'expired' automatically."""
    today = dt.date.today().isoformat()
    with connect() as c:
        cur = c.execute("UPDATE engagements SET status='expired' WHERE status='active' AND valid_to<?", (today,))
        return cur.rowcount


def purge_expired_scans(today: dt.date | None = None) -> int:
    """Delete results 30 days after expiry or recorded revocation. Keep audit metadata.

    Called on each app run and by scripts/cleanup.py (schedule daily for unattended cleanup).
    Global AI caches are invalidated conservatively because legacy keys have no client ownership.
    """
    from core.db import ROOT

    cutoff = ((today or dt.datetime.now(dt.timezone.utc).date()) - dt.timedelta(days=30)).isoformat()
    with connect() as c:
        c.execute("PRAGMA secure_delete = ON")
        c.execute("BEGIN IMMEDIATE")
        due = c.execute(
            "SELECT e.id FROM engagements e WHERE e.valid_to<=? OR "
            "(e.status='revoked' AND EXISTS (SELECT 1 FROM audit_log a "
            "WHERE a.engagement_id=e.id AND a.action='engagement_revoked' AND date(a.ts)<=?))",
            (cutoff, cutoff)).fetchall()
        total = 0
        for e in due:
            count = c.execute("SELECT COUNT(*) FROM scans WHERE engagement_id=?", (e["id"],)).fetchone()[0]
            if not count:
                continue
            # Remove caches before committing deletion; retry safely if filesystem deletion fails.
            for name in ("ai.json", "explanations.json"):
                (ROOT / "data" / "cache" / name).unlink(missing_ok=True)
            c.execute("DELETE FROM finding_dismissals WHERE scan_id IN "
                      "(SELECT id FROM scans WHERE engagement_id=?)", (e["id"],))
            c.execute("DELETE FROM scans WHERE engagement_id=?", (e["id"],))
            audit.append(c, "scan_data_purged", engagement_id=e["id"], details={"scans_deleted": count})
            total += count
    return total
