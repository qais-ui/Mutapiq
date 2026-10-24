import pytest


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    from core import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db, "KEY_PATH", tmp_path / ".key")
    monkeypatch.setenv("MUTABIQ_NO_CACHE", "1")
    db.init_db()
    return tmp_path


@pytest.fixture
def clients(isolated_db):
    from core.engagement import create_client, create_engagement, create_user
    rows = []
    for i in range(2):
        cid = create_client(f"Client {i}", f"CR-{i}")
        uid = create_user(f"client{i}", "test-password", "client", cid)
        eng = create_engagement(f"ENG-{i}", cid, ["example.jo"], "2000-01-01", "2999-01-01", "A", "CEO")
        rows.append((cid, uid, eng["id"]))
    return rows
