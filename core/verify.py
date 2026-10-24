"""Domain ownership proof: the client publishes the engagement's token in DNS (or a file)."""
from __future__ import annotations

import os

import dns.resolver
import requests

# Demo-only escape hatch for offline rehearsal. NEVER set this on stage if you can avoid it;
# the pitch is stronger when the real DNS check passes.
OFFLINE_DEMO = os.environ.get("MUTABIQ_OFFLINE_VERIFY") == "1"


def dns_token_ok(domain: str, token: str) -> bool:
    try:
        r = dns.resolver.Resolver()
        r.lifetime = 6
        for name in (domain, f"_mutabiq.{domain}"):
            try:
                if any(token in a.to_text().strip('"') for a in r.resolve(name, "TXT")):
                    return True
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return False


LOCAL_HOSTS = {"127.0.0.1", "localhost"}


def file_token_ok(domain: str, token: str) -> bool:
    """Use this for hosts where you can't edit DNS (e.g. *.onrender.com): serve the token at
    /.well-known/mutabiq.txt. The demo site does this from the MUTABIQ_VERIFY_TOKEN env var."""
    urls = [f"https://{domain}/.well-known/mutabiq.txt"]
    if domain in LOCAL_HOSTS:
        urls = [f"http://{domain}:{os.environ.get('MUTABIQ_LOCAL_PORT', '5001')}/.well-known/mutabiq.txt"]
    for url in urls:
        try:
            r = requests.get(url, timeout=8)
            if r.ok and token in r.text:
                return True
        except requests.RequestException:
            continue
    return False


def ownership_verified(domain: str, token: str) -> tuple[bool, str]:
    if dns_token_ok(domain, token):
        return True, "dns_txt"
    if file_token_ok(domain, token):
        return True, "well_known_file"
    if OFFLINE_DEMO:
        return True, "offline_demo_override"
    return False, "not_found"
