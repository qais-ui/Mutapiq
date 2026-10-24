-- Mutabiq database (SQLite). Rebuild any time with:  python scripts/seed.py
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_name      TEXT NOT NULL,
    commercial_reg  TEXT NOT NULL,          -- السجل التجاري
    contact_email   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,          -- bcrypt
    display_name    TEXT,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'client')),
    client_id       INTEGER REFERENCES clients(id)   -- NULL for Mutabiq admins
);

CREATE TABLE IF NOT EXISTS engagements (
    id              TEXT PRIMARY KEY,       -- ENG-2026-014
    client_id       INTEGER NOT NULL REFERENCES clients(id),
    valid_from      TEXT NOT NULL,          -- YYYY-MM-DD
    valid_to        TEXT NOT NULL,
    allowed_scans   TEXT NOT NULL,          -- comma list: passive_web,infra_map
    signatory_name  TEXT NOT NULL,
    signatory_title TEXT NOT NULL,
    contract_file   TEXT,                   -- path to the signed authorization PDF
    verify_token    TEXT NOT NULL,          -- value the client puts in DNS TXT
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'revoked')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scope_targets (
    engagement_id   TEXT NOT NULL REFERENCES engagements(id),
    domain          TEXT NOT NULL,
    PRIMARY KEY (engagement_id, domain)
);

CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id   TEXT NOT NULL REFERENCES engagements(id),
    target          TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    report_enc      BLOB                    -- Fernet-encrypted JSON report
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    user_id         INTEGER,
    action          TEXT NOT NULL,          -- scan_attempt, engagement_created, report_downloaded ...
    target          TEXT,
    engagement_id   TEXT,
    allowed         INTEGER,
    details         TEXT,                   -- JSON
    prev_hash       TEXT NOT NULL,
    hash            TEXT NOT NULL           -- sha256(prev_hash + canonical row)
);

CREATE TABLE IF NOT EXISTS finding_dismissals (
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    finding_id      TEXT NOT NULL,
    reason_enc      BLOB NOT NULL,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (scan_id, finding_id)
);
