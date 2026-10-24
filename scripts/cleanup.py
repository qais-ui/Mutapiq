"""Run daily using Task Scheduler/cron: python scripts/cleanup.py. Does not need Ollama."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import init_db
from core.engagement import expire_old, purge_expired_scans

if __name__ == "__main__":
    init_db()
    expired = expire_old()
    deleted = purge_expired_scans()
    print(f"Expired contracts: {expired}; deleted scans: {deleted}")
