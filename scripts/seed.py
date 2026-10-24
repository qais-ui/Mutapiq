"""Rebuild the database with the demo engagement.  python scripts/seed.py

Creates:
  admin  / admin123      — Mutabiq team (admin page)
  shifa  / shifa123      — Shifa Health client user
  ENG-2026-014           — Shifa Health engagement, scope = demo domain + 127.0.0.1 (local demo)
Set MUTABIQ_DEMO_DOMAIN to your deployed demo site's hostname before running.
Change these passwords before showing the app to anyone outside the team.
"""
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import DB_PATH, init_db  # noqa: E402
from core.engagement import create_client, create_engagement, create_user  # noqa: E402

DEMO_DOMAIN = os.environ.get("MUTABIQ_DEMO_DOMAIN", "shifa-demo.onrender.com")

if DB_PATH.exists():
    DB_PATH.unlink()
init_db()

admin = create_user("admin", "admin123", "admin", display_name="Mutabiq Admin")
client = create_client("Shifa Health LLC", "CR-123456", "it@shifa.example")
create_user("shifa", "shifa123", "client", client_id=client, display_name="Shifa Health — IT Manager")

today = dt.date.today()
eng = create_engagement(
    "ENG-2026-014", client, [DEMO_DOMAIN, "127.0.0.1"],
    today.isoformat(), (today + dt.timedelta(days=90)).isoformat(),
    "Dr. Lina Haddad", "CEO, Shifa Health LLC (fictional)",
    contract_file="docs/sample_authorization_letter.md", admin_id=admin,
)
print("Seeded", DB_PATH)
print("Engagement:", eng["id"], "scope:", eng["scope"])
print("Ask the client to add this DNS TXT record on", DEMO_DOMAIN, "(or _mutabiq." + DEMO_DOMAIN + "):")
print("   ", eng["verify_token"])
# Saved so the local demo site can serve it automatically (START_MUTABIQ.bat relies on this).
(DB_PATH.parent / "demo_token.txt").write_text(eng["verify_token"], encoding="utf-8")
