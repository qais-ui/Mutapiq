"""Streamlit's real script runner with network/LLM boundaries mocked, not a browser test."""
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from core import ai, db, gate, infra, llm, scanner
from core.engagement import get_engagement, set_status
from core.schemas import CompanyProfile, ScanResult


def test_client_scan_dismiss_restore_and_report(clients, monkeypatch):
    monkeypatch.setattr(llm, "ollama_status", lambda: {
        "up": False, "models": [], "llm_ready": False, "embed_ready": False})
    monkeypatch.setattr(infra, "map_infra", lambda *args: {})
    monkeypatch.setattr(scanner, "scan", lambda *args, **kwargs: ScanResult(
        target="example.jo", https={"https_ok": False}))
    monkeypatch.setattr(gate, "authorize_scan", lambda *args, **kwargs: SimpleNamespace(
        allowed=True, checks={}, verify_method="test", engagement=get_engagement(clients[0][2])))
    with db.connect() as c:
        user = dict(c.execute("SELECT * FROM users WHERE id=?", (clients[0][1],)).fetchone())
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20)
    app.session_state["user"] = user
    app.run()
    assert not app.exception
    app.session_state["profile"] = CompanyProfile(name="Test", domain="example.jo")
    app.run()
    next(b for b in app.button if b.label == "Run authorised scan").click().run()
    assert not app.exception
    assert app.session_state["scan_id"]
    # The finding appears in both All and Jordan; operate on the first copy.
    next(t for t in app.text_area if t.label == "Reason (5–2000 characters)").input(
        "Internal endpoint, manually confirmed safe")
    next(b for b in app.button if b.label == "Dismiss as false positive").click().run()
    assert not app.exception
    assert "NO_HTTPS" not in {f.id for f in app.session_state["report"].findings}
    next(b for b in app.button if b.label == "Restore finding").click().run()
    assert not app.exception
    assert "NO_HTTPS" in {f.id for f in app.session_state["report"].findings}
    # Arabic labels and report path use the same persisted review state.
    app.sidebar.radio[0].set_value("ar").run()
    assert not app.exception


def test_ended_contract_keeps_audit_export_available(clients, monkeypatch):
    monkeypatch.setattr(llm, "ollama_status", lambda: {
        "up": False, "models": [], "llm_ready": False, "embed_ready": False})
    set_status(clients[0][2], "revoked")
    with db.connect() as c:
        user = dict(c.execute("SELECT * FROM users WHERE id=?", (clients[0][1],)).fetchone())
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20)
    app.session_state["user"] = user
    app.run()
    assert not app.exception
    assert any("No active contract" in warning.value for warning in app.warning)
    # Download controls exist before the no-active-contract stop.
    assert len(app.get("download_button")) == 1
