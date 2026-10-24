"""Law-first screening of public disclosures plus unverified governance answers.

This module never imports or calls the vulnerability scanner or security rules.
It reads only the included, owned demo site and never accepts an external target.
"""
from datetime import datetime, timezone
from html import escape
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from legal_catalog import AREAS, CHECKS
from legal_models import BusinessProfile, LegalFinding, LegalReport

BASE = "http://127.0.0.1:5001"
DEMO_TARGET = "Included Shifa Health demo website"
STATUS = {
    "evidence_found": ("Disclosure signal found", "عُثر على إشارة إفصاح"),
    "review_needed": ("Review needed", "تحتاج إلى مراجعة"),
    "needs_confirmation": ("Needs confirmation", "تحتاج إلى تأكيد"),
    "self_reported": ("Self-reported, unverified", "إقرار ذاتي غير متحقق منه"),
    "out_of_scope": ("Not selected by profile", "غير محدد وفق الملف"),
}
WARNINGS = [
    "Curated initial screening only: this is not every law, legal advice, a legal opinion or a compliance certification.",
    "Jordan is the only supported domestic jurisdiction. GDPR is conditional on Article 3 and the selected business facts.",
    "Public text signals are not proof of legal compliance or legal violations. Internal company, HR, tax and licensing records were not inspected.",
    "Source links include official authority directories and legal repositories, not only consolidated statutes. Current amendments, implementing rules, legal form and sector-specific requirements need professional verification.",
    "Questionnaire answers and the fictional company profile are self-reported assumptions, not independently verified evidence. Answers stay in this session.",
]


def _read_page(url: str, kind: str) -> tuple[dict, BeautifulSoup]:
    if (urlparse(url).scheme, urlparse(url).netloc) != ("http", "127.0.0.1:5001"):
        raise ValueError("Only the included local demo site may be read.")
    response = requests.get(url, timeout=8, allow_redirects=False)
    response.raise_for_status()
    if response.is_redirect:
        raise RuntimeError("The demo page redirected; redirects are not followed.")
    if len(response.content) > 1_000_000:
        raise RuntimeError("The demo document is too large.")
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else kind.title()
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return {"url": url, "title": title, "kind": kind,
            "text": re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:40000]}, soup


def _collect_documents() -> tuple[list[dict], list[str]]:
    # Retain the existing permission gate, in the isolated demo database only.
    from core.db import DB_PATH, connect
    from core.gate import authorize_scan
    from pathlib import Path
    expected = Path(__file__).resolve().parent / "db" / "preview" / "mutabiq.db"
    if DB_PATH.resolve() != expected.resolve():
        raise PermissionError("Legal demo must use the isolated preview database.")
    with connect() as connection:
        row = connection.execute(
            "SELECT id, role, client_id FROM users WHERE username = ?", ("shifa",)
        ).fetchone()
    if not row or not authorize_scan(dict(row), "127.0.0.1").allowed:
        raise PermissionError("The included demo site's authorization could not be verified.")
    homepage, soup = _read_page(BASE + "/", "home")
    documents, warnings, seen = [homepage], [], {BASE + "/"}
    for link in soup.find_all("a", href=True):
        label = (link.get_text(" ", strip=True) + " " + link["href"]).lower()
        kind = next((kind for kind, terms in {
            "privacy": ("privacy", "خصوصية"),
            "terms": ("terms", "refund", "cancel", "شروط"),
            "contact": ("contact", "اتصل"),
            "about": ("about", "حول"),
        }.items() if any(term in label for term in terms)), None)
        url = urljoin(BASE + "/", link["href"]).split("#")[0]
        if not kind or url in seen or urlparse(url).netloc != "127.0.0.1:5001":
            continue
        seen.add(url)
        try:
            document, _ = _read_page(url, kind)
            documents.append(document)
        except (requests.RequestException, ValueError, RuntimeError):
            warnings.append(f"Linked {kind} page could not be read; absent disclosures must not be inferred from that failure.")
        if len(seen) >= 6:
            break
    return documents, warnings


def _applicability(check, profile):
    key = check.applicability
    if key == "eu":
        if profile.eu_activity == "no":
            return "out_of_scope", "No EU establishment, targeted offering or monitoring was selected. This is a profile assumption, not a legal determination.", "لم يُحدد نشاط أوروبي في الملف؛ هذا افتراض وليس حكماً قانونياً."
        if profile.eu_activity == "unknown":
            return "needs_confirmation", "First assess GDPR Article 3: EU establishment, offering goods/services to people in the EU, or monitoring their behaviour. Website availability alone does not establish scope.", "يجب أولاً تقييم نطاق المادة 3 من GDPR؛ إتاحة الموقع وحدها لا تثبت الانطباق."
    if (key == "employees" and not profile.has_employees) or (key == "consumers" and not profile.serves_consumers):
        return "out_of_scope", "Not selected by this business profile. Verify the underlying facts before excluding a legal duty.", "غير محدد وفق الملف المختار؛ تحقق من الحقائق قبل استبعاد الالتزام."
    if key in ("health", "finance") and profile.sector != key:
        return "out_of_scope", "This activity was not selected in the demo profile. Other activities may change legal scope.", "لم يُحدد هذا النشاط في الملف التجريبي؛ قد تغير الأنشطة الأخرى نطاق الالتزام."
    return None


def _assess(check, profile, documents, answers):
    scope = _applicability(check, profile)
    if scope:
        return LegalFinding(check, *scope)
    response = answers.get(check.id, {})
    note = str(response.get("note", "")).strip()[:2000]
    answer = response.get("answer", "unknown")
    if answer in ("in_place", "gap", "not_applicable") and note:
        reasons = {
            "in_place": ("The business reports this control is in place. The note is unverified; no supporting internal records were inspected.", "تقر الشركة بوجود الإجراء؛ الملاحظة ذاتية ولم تُفحص السجلات الداعمة."),
            "gap": ("The business reports a gap. Confirm the exact applicable duty and remediation with an adviser.", "أبلغت الشركة عن فجوة؛ يجب تأكيد الالتزام الدقيق وخطة المعالجة مع المختص."),
            "not_applicable": ("The business reports non-applicability. This remains a self-reported scope claim, not a legal exclusion.", "تقر الشركة بعدم الانطباق؛ هذا ادعاء ذاتي وليس استبعاداً قانونياً مؤكداً."),
        }
        reason, reason_ar = reasons[answer]
        return LegalFinding(check, "review_needed" if answer == "gap" else "self_reported",
                            reason, reason_ar, note=note)
    if answer != "unknown" and not note:
        return LegalFinding(check, "needs_confirmation",
                            "An answer needs a supporting note or record reference. No internal control has been verified.",
                            "تحتاج الإجابة إلى ملاحظة داعمة أو مرجع للسجل؛ لم يتم التحقق من الإجراء.")
    if not check.terms:
        return LegalFinding(check, "needs_confirmation",
                            "This cannot be established from public website text. Review the relevant internal documents and applicable legal scope.",
                            "لا يمكن إثبات ذلك من نص الموقع العام؛ راجع السجلات الداخلية ونطاق الالتزام.")
    relevant = [doc for doc in documents if doc["kind"] == "privacy"] if check.category in ("privacy", "gdpr") else documents
    if not relevant:
        return LegalFinding(check, "needs_confirmation",
                            "No readable linked privacy document was available. Its contents could not be assessed.",
                            "لم تتوفر سياسة خصوصية مرتبطة قابلة للقراءة؛ لا يمكن تقييم محتواها.")
    for doc in relevant:
        for term in check.terms:
            match = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", doc["text"], flags=re.I)
            if match:
                quote = doc["text"][max(0, match.start() - 100):match.end() + 180]
                return LegalFinding(check, "evidence_found",
                                    "A related phrase was found in the reviewed public text. This is a disclosure signal, not proof of accuracy, completeness or compliance.",
                                    "عُثر على عبارة ذات صلة في النص العام؛ هذه إشارة إفصاح وليست إثباتاً لاكتماله أو للامتثال.",
                                    evidence=quote, evidence_url=doc["url"])
    return LegalFinding(check, "review_needed",
                        "No matching disclosure phrase was located in the reviewed public text. Manually assess the full applicable requirement before calling this a legal gap.",
                        "لم تُرصد عبارة الإفصاح في النص الذي تمت مراجعته؛ يجب تقييم المتطلب كاملاً قبل اعتبارها فجوة قانونية.")


def _validate_profile(profile):
    if profile.jurisdiction != "JO":
        raise ValueError("Only the Jordan-based demo is supported.")
    if profile.sector not in ("health", "retail", "finance", "services"):
        raise ValueError("Unsupported demo business sector.")
    if profile.eu_activity not in ("yes", "no", "unknown"):
        raise ValueError("Choose yes, no or unknown for EU activity.")


def run_legal_review(profile: BusinessProfile) -> LegalReport:
    _validate_profile(profile)
    documents, warnings = _collect_documents()
    return LegalReport(
        profile=profile,
        findings=[_assess(check, profile, documents, {}) for check in CHECKS],
        documents=documents, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        warnings=WARNINGS + warnings,
    )


def update_review(report: LegalReport, responses: dict[str, dict]) -> LegalReport:
    _validate_profile(report.profile)
    return LegalReport(
        profile=report.profile,
        findings=[_assess(check, report.profile, report.documents, responses) for check in CHECKS],
        documents=report.documents, created_at=report.created_at, warnings=report.warnings,
    )


def export_legal_report(report: LegalReport, lang: str = "en") -> str:
    ar = lang == "ar"
    e = lambda text: escape(str(text), quote=True)
    title = "مراجعة الأعمال والحوكمة" if ar else "Business & governance review"
    pieces = []
    for finding in report.findings:
        c = finding.check
        requirement = c.requirement_ar if ar else c.requirement
        action = c.action_ar if ar else c.action
        evidence = f"<blockquote>{e(finding.evidence)}</blockquote>" if finding.evidence else ""
        note = f"<p><b>{'إقرار ذاتي' if ar else 'Self-reported note'}:</b> {e(finding.note)}</p>" if finding.note else ""
        pieces.append(
            f"<article><small>{e(AREAS[c.category]['ar' if ar else 'en'])}</small>"
            f"<h2>{e(c.title_ar if ar else c.title)}</h2>"
            f"<b>{e(STATUS[finding.status][int(ar)])}</b>"
            f"<p>{e(c.law)} · {e(c.reference)}</p>"
            f"<p>{e(requirement)}</p><p>{e(finding.reason_ar if ar else finding.reason)}</p>"
            f"{evidence}{note}<p>{e(action)}</p>"
            f"<a href='{e(c.source_url)}'>{'المصدر القانوني' if ar else 'Legal source'}</a></article>"
        )
    warnings = "".join(f"<li>{e(w)}</li>" for w in report.warnings)
    return (
        f"<!doctype html><html lang='{'ar' if ar else 'en'}' dir='{'rtl' if ar else 'ltr'}'>"
        "<head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Mutabiq — {e(title)}</title><style>"
        "body{max-width:950px;margin:40px auto;padding:0 20px;font:16px/1.6 system-ui;background:#f4eee3;color:#14302b}"
        "article{background:#fbf8f2;padding:24px;border:1px solid #ddd4c7;border-radius:16px;margin:16px 0}"
        "h1{font-size:2.3rem}h2{font-size:1.2rem}small{color:#596b64}a{color:#0f6e56}"
        "blockquote{border-inline-start:3px solid #c4532d;padding:12px;background:#f4eee3;white-space:pre-wrap}"
        "</style></head><body><p>MUTABIQ · DEMO</p>"
        f"<h1>{e(title)}</h1><p>{e(report.profile.name)} · Jordan · {e(report.created_at)}</p>"
        "<p>Fictional sample business. Initial legal screening, not a legal opinion or a compliance certification.</p>"
        "<p>Disclosure signals are not verified compliance; questionnaire answers are unverified self-reports.</p>"
        f"<ul>{warnings}</ul>{''.join(pieces)}</body></html>"
    )
