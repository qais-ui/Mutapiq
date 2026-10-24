"""Download the public cloud IP-range files used by core/infra.py. Run once with internet:
    python scripts/update_cloud_ranges.py
"""
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "cloud_ranges"
SOURCES = {
    "aws.json": "https://ip-ranges.amazonaws.com/ip-ranges.json",
    "gcp.json": "https://www.gstatic.com/ipranges/cloud.json",
}

OUT.mkdir(parents=True, exist_ok=True)
for name, url in SOURCES.items():
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    (OUT / name).write_text(r.text)
    print(f"saved {name} ({len(r.text) // 1024} KB)")
# Azure publishes a weekly JSON (ServiceTags_Public_*.json) behind a download page:
# https://www.microsoft.com/en-us/download/details.aspx?id=56519 — download it manually
# into data/cloud_ranges/azure.json if you need Azure region detection.
