"""The authorization gate. EVERY scan goes through authorize_scan(); nothing calls scanner.scan() directly.

Five checks, all must pass:
  1. authenticated   — a logged-in client user
  2. active_contract — an engagement for that client, status active, today within its dates
  3. in_scope        — the exact domain is listed in that engagement
  4. owner_verified  — the engagement token is published in the domain's DNS (or /.well-known file)
  5. scan_allowed    — the requested scan type is permitted by the contract
Every attempt, allowed or blocked, is written to the hash-chained audit log.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core import audit
from core.engagement import active_engagements_for_client
from core.scanner import normalize_target
from core.verify import ownership_verified


class ScanBlocked(PermissionError):
    def __init__(self, checks: dict):
        self.checks = checks
        failed = [k for k, v in checks.items() if not v]
        super().__init__(f"Scan blocked: {', '.join(failed)}")


@dataclass
class GateResult:
    allowed: bool
    checks: dict
    engagement: dict | None = None
    verify_method: str | None = None
    failed: list[str] = field(default_factory=list)


def authorize_scan(user: dict | None, target: str, scan_type: str = "passive_web",
                   engagement_id: str | None = None) -> GateResult:
    domain = normalize_target(target)
    checks = {"authenticated": False, "active_contract": False, "in_scope": False,
              "owner_verified": False, "scan_allowed": False}
    eng, method = None, None

    if user and user.get("role") == "client" and user.get("client_id"):
        checks["authenticated"] = True
        engs = active_engagements_for_client(user["client_id"])
        if engagement_id is not None:
            engs = [e for e in engs if e["id"] == engagement_id]
        checks["active_contract"] = bool(engs)
        eng = next((e for e in engs if domain in e["scope"]), None)
        checks["in_scope"] = eng is not None
        if eng:
            ok, method = ownership_verified(domain, eng["verify_token"])
            checks["owner_verified"] = ok
            checks["scan_allowed"] = scan_type in eng["allowed_scans"]

    allowed = all(checks.values())
    audit.log("scan_attempt", user.get("id") if user else None, domain,
              eng["id"] if eng else None, allowed, {"checks": checks, "scan_type": scan_type, "verify": method})
    return GateResult(allowed, checks, eng, method, [k for k, v in checks.items() if not v])


def require_scan(user: dict | None, target: str, scan_type: str = "passive_web") -> GateResult:
    res = authorize_scan(user, target, scan_type)
    if not res.allowed:
        raise ScanBlocked(res.checks)
    return res
