"""Role + language report rendering — owned by the teammate.
HTML via Jinja2 always; PDF via WeasyPrint when it is installed (it needs Pango on the machine).
If WeasyPrint is missing, the UI offers the HTML file — open it and Print → Save as PDF."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.schemas import Report

ROOT = Path(__file__).resolve().parent.parent
ENV = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))

TEXT = {
    "en": {"title": "Compliance assessment", "confidential": "Confidential", "prepared_for": "Prepared for",
           "under": "under engagement", "summary": "Summary", "score_note": "technical compliance score (detected issues only)",
           "framework": "Framework", "applies": "Applies?", "why": "Why", "yes": "Yes", "no": "Not now",
           "top_actions": "Top 5 actions", "findings": "Findings", "evidence": "Evidence", "source": "Basis",
           "refs": "References", "privacy_draft": "Draft privacy notice (for lawyer review)",
           "sev": {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"},
           "src": {"detected": "detected by scan", "user_confirmed": "confirmed by you", "profile": "from your answers"},
           "roles": {"owner": "Executive summary", "developer": "Technical fix list", "legal": "Legal & DPO report"},
           "disclaimer": "This report is automated guidance, not legal advice. Findings marked 'article to be confirmed' "
                         "must be checked against the official text. A qualified lawyer should review it before you act on it."},
    "ar": {"title": "تقييم الامتثال", "confidential": "سري", "prepared_for": "أُعد لصالح", "under": "بموجب الاتفاقية",
           "summary": "الملخص", "score_note": "درجة الامتثال التقني (الملاحظات المكتشفة فقط)", "framework": "الإطار",
           "applies": "ينطبق؟", "why": "السبب", "yes": "نعم", "no": "ليس حالياً", "top_actions": "أهم 5 إجراءات",
           "findings": "الملاحظات", "evidence": "الدليل", "source": "المصدر", "refs": "المراجع",
           "privacy_draft": "مسودة إشعار الخصوصية (لمراجعة المحامي)",
           "sev": {"critical": "حرجة", "high": "عالية", "medium": "متوسطة", "low": "منخفضة"},
           "src": {"detected": "اكتشفها الفحص", "user_confirmed": "أكدتموها", "profile": "من إجاباتكم"},
           "roles": {"owner": "ملخص تنفيذي", "developer": "قائمة الإصلاحات التقنية", "legal": "التقرير القانوني"},
           "disclaimer": "هذا التقرير إرشاد آلي وليس استشارة قانونية. يجب التحقق من المراجع المعلّمة بعبارة "
                         "«المادة قيد التحقق» من النص الرسمي، ويجب أن يراجعه محامٍ مؤهل قبل الاعتماد عليه."},
}


def render_html(report: Report, explanations: dict[str, dict], role: str, lang: str,
                privacy_draft: str | None = None, dismissals: list[dict] | None = None) -> str:
    t = {**TEXT[lang], "role_label": TEXT[lang]["roles"][role]}
    items = [{"f": f, "ex": explanations[f.id],
              "title": f.title_ar if lang == "ar" and f.title_ar else f.title,
              "evidence_str": json.dumps(f.evidence, ensure_ascii=False, default=str)[:300]}
             for f in report.findings if f.id in explanations]
    return ENV.get_template("report.html").render(report=report, items=items, role=role, lang=lang, t=t,
                                                  privacy_draft=privacy_draft,
                                                  dismissals=dismissals or [],
                                                  generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))


def to_pdf(html: str) -> bytes | None:
    try:
        from weasyprint import HTML
        return HTML(string=html, base_url=str(ROOT)).write_pdf()
    except Exception:  # noqa: BLE001 — not installed / missing system libs
        return None
