import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from core import ai, audit, db, llm, review
from core.engagement import purge_expired_scans, set_status
from core.report import render_html
from core.rules import evaluate
from core.schemas import CompanyProfile, ScanResult


def save_scan(engagement_id):
    report = evaluate(CompanyProfile(name="Test", domain="example.jo"),
                      ScanResult(target="example.jo", https={"https_ok": False}))
    report.engagement_id = engagement_id
    with db.connect() as c:
        return c.execute("INSERT INTO scans (engagement_id,target,report_enc) VALUES (?,?,?)",
                         (engagement_id, "example.jo", db.encrypt(report.model_dump_json()))).lastrowid


def test_retention_boundary_and_audit_preservation(clients, monkeypatch, isolated_db):
    ids = [save_scan(eid) for _, _, eid in clients]
    with db.connect() as c:
        c.execute("UPDATE engagements SET valid_to='2026-09-24' WHERE id=?", (clients[0][2],))
        c.execute("UPDATE engagements SET valid_to='2026-09-25' WHERE id=?", (clients[1][2],))
    review.dismiss(clients[0][1], ids[0], "NO_HTTPS", "Confirmed internal-only test fixture")
    cache = isolated_db / "data" / "cache"
    cache.mkdir(parents=True)
    (cache / "ai.json").write_text('{"private":"data"}')
    (cache / "explanations.json").write_text("{}")
    monkeypatch.setattr(db, "ROOT", isolated_db)
    assert purge_expired_scans(dt.date(2026, 10, 24)) == 1
    assert purge_expired_scans(dt.date(2026, 10, 24)) == 0
    with db.connect() as c:
        assert [r[0] for r in c.execute("SELECT id FROM scans")] == [ids[1]]
        assert c.execute("SELECT COUNT(*) FROM finding_dismissals").fetchone()[0] == 0
    assert not (cache / "ai.json").exists()
    assert audit.entries(1)[0]["action"] == "scan_data_purged"
    assert audit.verify_chain()["ok"]


def test_retention_uses_revocation_date(clients):
    save_scan(clients[0][2])
    set_status(clients[0][2], "revoked")
    today = dt.datetime.now(dt.timezone.utc).date()
    assert purge_expired_scans(today + dt.timedelta(days=29)) == 0
    assert purge_expired_scans(today + dt.timedelta(days=30)) == 1


def test_audit_export_has_no_other_clients_or_global_events(clients):
    _, user, eng = clients[0]
    for i in range(205):
        audit.log("client_event", user, engagement_id=eng, details={"n": i})
    audit.log("secret_other_company", clients[1][1], engagement_id=clients[1][2])
    audit.log("login_failed", details={"username": "unrelated"})
    out = json.loads(audit.export_for_client(user))
    assert len(out["entries"]) == 206  # includes engagement creation, no default 200-row truncation
    assert {e["engagement_id"] for e in out["entries"]} == {eng}
    assert all("hash" not in e for e in out["entries"])
    with pytest.raises(PermissionError):
        audit.export_for_client(user, clients[1][2])
    with pytest.raises(PermissionError):
        audit.export_for_client(-1)
    set_status(eng, "revoked")
    assert json.loads(audit.export_for_client(user))["entries"]


def test_dismissal_is_owned_encrypted_reversible_and_scan_scoped(clients):
    _, user, eng = clients[0]
    scan = save_scan(eng)
    reason = "Confirmed false positive after manual TLS review"
    review.dismiss(user, scan, "NO_HTTPS", reason)
    assert review.dismissals(user, scan)[0]["reason"] == reason
    with db.connect() as c:
        row = c.execute("SELECT reason_enc FROM finding_dismissals").fetchone()
        assert reason.encode() not in row[0]
    assert reason not in json.dumps(audit.entries())
    with pytest.raises(PermissionError):
        review.dismiss(clients[1][1], scan, "NO_HTTPS", reason)
    with pytest.raises(PermissionError):
        review.dismissals(clients[1][1], scan)
    with pytest.raises(PermissionError):
        review.restore(clients[1][1], scan, "NO_HTTPS")
    assert review.dismissals(user, save_scan(eng)) == []
    review.restore(user, scan, "NO_HTTPS")
    assert review.dismissals(user, scan) == []
    assert audit.verify_chain()["ok"]


@pytest.mark.parametrize("finding,reason", [
    ("NO_HTTPS", " "), ("NO_HTTPS", "x" * 2001), ("MADE_UP", "Valid reason"),
    ("BREACH_PROCESS", "Not a detected finding"),
])
def test_invalid_dismissals_are_rejected(clients, finding, reason):
    with pytest.raises(ValueError):
        review.dismiss(clients[0][1], save_scan(clients[0][2]), finding, reason)


def test_score_and_report_show_client_review_not_silent_removal():
    p, s = CompanyProfile(name="X", domain="x"), ScanResult(target="x")
    before = evaluate(p, s)
    after = evaluate(p, s, dismissed={"NO_HTTPS", "BREACH_PROCESS"})
    assert after.score > before.score
    assert "NO_HTTPS" not in {f.id for f in after.findings}
    assert "BREACH_PROCESS" in {f.id for f in after.findings}
    html = render_html(after, {}, "owner", "en", dismissals=[
        {"finding_id": "NO_HTTPS", "reason": "<script>alert(1)</script>", "user_id": 1, "created_at": "2026"}])
    assert "not independently verified" in html
    assert "&lt;script&gt;" in html and "<script>" not in html


def test_concurrent_audit_writes_keep_chain(isolated_db):
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: audit.log("parallel", details={"n": n}), range(32)))
    assert len(audit.entries()) == 32
    assert audit.verify_chain()["ok"]


def test_profile_false_strings_and_cache_are_not_mutated(monkeypatch):
    result = {"sector": "ecommerce", "is_government": "false", "expanding_to_eu": "false", "notes": "unknown"}
    monkeypatch.setattr(ai, "_ai", lambda *args: result)
    profile, meta = ai.profile_from_text("shop", "x")
    assert not profile.is_government and not profile.expanding_to_eu
    assert meta["notes"] == "unknown" and result["notes"] == "unknown"


@pytest.mark.parametrize("quote", ["", "fake", "We collect your name and email but keep it forever"])
def test_policy_requires_full_nonempty_verbatim_quote(monkeypatch, quote):
    text = "We collect your name and email. We use it for bookings. " * 8
    monkeypatch.setattr(ai, "_ai", lambda *args: {"elements": {
        k: {"present": True, "quote": quote} for k in ai.POLICY_ELEMENTS}})
    assert len(ai.analyze_privacy_policy(text)["missing"]) == len(ai.POLICY_ELEMENTS)


def test_policy_false_string_is_not_present(monkeypatch):
    text = "We collect your name and email. " * 10
    monkeypatch.setattr(ai, "_ai", lambda *args: {"elements": {
        k: {"present": "false", "quote": "We collect your name"} for k in ai.POLICY_ELEMENTS}})
    assert "data_categories" in ai.analyze_privacy_policy(text)["missing"]


@pytest.mark.parametrize("answer", ["A made-up claim [99].", "An unsupported answer without citations."])
def test_qa_rejects_invalid_or_missing_citations(monkeypatch, answer):
    monkeypatch.setattr(ai, "search", lambda *args, **kwargs: [
        {"source": "PDPL", "text": "Grounded passage", "article": "11"}])
    monkeypatch.setattr(ai, "_ai", lambda *args: {"answer": answer})
    assert ai.ask("question")["generated_by"] is None


@pytest.mark.parametrize("update", [
    {"summary": None}, {"what_to_do": [1, 2]}, {"citations": ["fake"]}, {"citations": None},
])
def test_explanation_rejects_malformed_output(update):
    f = evaluate(CompanyProfile(name="X", domain="x"), ScanResult(target="x")).findings[0]
    ans = {"summary": "A finding", "why_it_matters": "Some risk", "what_to_do": ["Fix it", "Retest"],
           "citations": f.refs}
    assert not llm._valid({**ans, **update}, f, "en")


def test_ollama_requires_exact_model_tag(monkeypatch):
    class Response:
        def json(self):
            return {"models": [{"name": "qwen2.5:0.5b"}, {"name": "bge-m3:latest"}]}
    monkeypatch.setattr(llm.requests, "get", lambda *args, **kwargs: Response())
    assert not llm.ollama_status()["llm_ready"]
