"""Small, isolated demo surface over Mutabiq's existing security engine.

No external target or client identifier is accepted from a visitor. The full
application and its database are not exposed by this public demo.
"""
from pathlib import Path

from core.db import DB_PATH, connect
from core.gate import authorize_scan
from core.llm import explain, ollama_status
from core.report import render_html
from core.rules import evaluate
from core.scanner import scan
from core.schemas import CompanyProfile, Finding, Report

DEMO_NAME = "Shifa Health"
DEMO_TARGET = "127.0.0.1"
DEMO_DB = Path(__file__).resolve().parent / "db" / "preview" / "mutabiq.db"


def run_demo_scan() -> Report:
    if DB_PATH.resolve() != DEMO_DB.resolve():
        raise PermissionError("The demo requires its isolated preview database.")
    with connect() as connection:
        row = connection.execute(
            "SELECT id, role, client_id FROM users WHERE username = ?", ("shifa",)
        ).fetchone()
    if not row:
        raise RuntimeError("Demo workspace is not initialized. Restart the app workflow.")
    gate = authorize_scan(dict(row), DEMO_TARGET)
    if not gate.allowed:
        raise PermissionError("The demo authorization could not be verified. Restart the demo workspace.")
    result = scan(DEMO_TARGET, use_browser=False, base_url="http://127.0.0.1:5001")
    if result.errors:
        raise RuntimeError("The included demo site could not be scanned: " + "; ".join(result.errors))
    profile = CompanyProfile(
        name=DEMO_NAME, domain=DEMO_TARGET, sector="health",
        is_critical_sector=True, data_types=["basic", "health"],
        user_countries=["JO"], hosting_country="JO",
        processing_is_core_activity=True,
    )
    report = evaluate(profile, result)
    report.engagement_id = "DEMO-WORKSPACE"
    return report


def explanations(report: Report, lang: str = "en") -> dict:
    return {finding.id: explain(finding, "owner", lang, use_llm=False) for finding in report.findings}


def export_report(report: Report, lang: str = "en") -> str:
    document = render_html(report, explanations(report, lang), "owner", lang)
    label = (
        "<aside style='padding:16px;background:#fff6df;color:#574315;font-family:sans-serif'>"
        "DEMO REPORT — Shifa Health is fictional. This report checks only the included local "
        "demo website. It is not legal advice or a compliance certification.</aside>"
    )
    # Preserve the existing full report, with an explicit demo label in exports too.
    index = document.find(">", document.find("<body")) + 1
    return document[:index] + label + document[index:] if index > 0 else label + document


def explain_finding(finding: Finding, lang: str = "en") -> dict:
    return explain(finding, "owner", lang, use_llm=True)


def ai_status() -> dict:
    return ollama_status()
