"""Run: python -m pytest -q   (uses a temporary database, no network needed)"""
import pytest

from core import audit  # noqa: E402
from core.db import connect, init_db  # noqa: E402
from core.engagement import create_client, create_engagement, create_user, check_login  # noqa: E402
from core.gate import authorize_scan  # noqa: E402
from core.rules import evaluate  # noqa: E402
from core.schemas import CompanyProfile, ScanResult  # noqa: E402

@pytest.fixture(autouse=True)
def user(isolated_db):
    cid = create_client("Test Co", "CR-1")
    create_user("t", "pw", "client", cid)
    create_engagement("ENG-T", cid, ["example.jo"], "2000-01-01", "2999-01-01", "A", "CEO")
    return check_login("t", "pw")


def test_out_of_scope_is_blocked_and_logged(user):
    r = authorize_scan(user, "not-ours.com")
    assert not r.allowed and "in_scope" in r.failed
    assert audit.entries(1)[0]["allowed"] == 0


def test_anonymous_is_blocked():
    assert not authorize_scan(None, "example.jo").allowed


def test_audit_chain_detects_tampering():
    assert audit.verify_chain()["ok"]
    with connect() as c:
        c.execute("UPDATE audit_log SET target='x' WHERE id=1")
    assert not audit.verify_chain()["ok"]


def test_rules_health_eu():
    p = CompanyProfile(name="X", domain="example.jo", sector="health", data_types=["health"],
                       user_countries=["JO", "DE"], hosting_country="US")
    s = ScanResult(target="example.jo", https={"https_ok": True, "http_redirects_to_https": True},
                   headers={"hsts": None, "csp": None}, privacy_policy={"found": False})
    ids = {f.id for f in evaluate(p, s).findings}
    assert {"DPO_REQUIRED", "DATA_HOSTED_OUTSIDE_JO", "EU_TRANSFER_TO_JORDAN", "NO_PRIVACY_POLICY",
            "MISSING_HSTS", "NCSC_FRAMEWORK_APPLIES"} <= ids


def test_user_correction_overrides_detection():
    p = CompanyProfile(name="X", domain="example.jo")
    s = ScanResult(target="example.jo", infra={"hosting_country": "DE"})
    assert "DATA_HOSTED_OUTSIDE_JO" in {f.id for f in evaluate(p, s).findings}
    assert "DATA_HOSTED_OUTSIDE_JO" not in {f.id for f in evaluate(p, s, {"hosting_country": "JO"}).findings}


# ---------------------------------------------------------------- AI layer (model mocked — no Ollama needed)
import core.ai as ai  # noqa: E402


def test_profile_from_text_validates_model_output(monkeypatch):
    monkeypatch.setattr(ai, "_call_ollama", lambda m: {
        "name": "Shifa", "sector": "health", "is_critical_sector": False, "is_government": False,
        "data_types": ["health", "basic", "made_up"], "user_countries": ["jo", "DE"], "hosting_country": "de",
        "expanding_to_eu": True, "employees": 12, "processing_is_core_activity": True, "notes": "employees guessed"})
    prof, meta = ai.profile_from_text("احنا تطبيق حجز عيادات", "shifa.jo")
    assert prof.data_types == ["health", "basic"] and prof.user_countries == ["JO", "DE"]
    assert prof.hosting_country == "DE" and meta["notes"] == "employees guessed"


def test_profile_from_text_offline(monkeypatch):
    monkeypatch.setattr(ai, "_call_ollama", lambda m: None)
    assert ai.profile_from_text("x", "d")[0] is None


def test_policy_analysis_rejects_fake_quotes(monkeypatch):
    text = "We collect your name and email. We use it to book appointments. " * 5
    elements = {k: {"present": True, "quote": "this sentence is not in the policy at all"} for k in ai.POLICY_ELEMENTS}
    elements["data_categories"] = {"present": True, "quote": "We collect your name and email"}
    monkeypatch.setattr(ai, "_call_ollama", lambda m: {"elements": elements})
    res = ai.analyze_privacy_policy(text)
    assert res["elements"]["data_categories"]["present"]
    assert "retention" in res["missing"]          # model claimed it, quote not found → not trusted


def test_ask_keeps_only_cited_sources(monkeypatch):
    monkeypatch.setattr(ai, "_call_ollama", lambda m: {"answer": "Yes, health data requires a DPO [1]. Guidance, not legal advice.", "used_sources": [1]})
    res = ai.ask("Do we need a DPO for health data?", "en", ["PDPL", "GDPR"])
    assert res["generated_by"] and [s["n"] for s in res["sources"]] == [1]


def test_incomplete_policy_becomes_finding():
    p = CompanyProfile(name="X", domain="example.jo", data_types=["health"])
    s = ScanResult(target="example.jo", privacy_policy={"found": True, "has_arabic": False,
                   "analysis": {"missing": ["retention", "dpo_contact"], "generated_by": "qwen2.5:7b-instruct"}})
    f = next(x for x in evaluate(p, s).findings if x.id == "PRIVACY_POLICY_INCOMPLETE")
    assert f.evidence["missing"] == ["retention", "dpo_contact"]
