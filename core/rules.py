"""Deterministic rule engine — owned by the security engine (Ahmad).

Rules decide WHAT applies and WHAT is wrong. The LLM never decides this; it only explains.
Input: CompanyProfile + ScanResult. Output: applicability list + findings.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from core.schemas import Applicability, CompanyProfile, Finding, Report, ScanResult

DATA = Path(__file__).resolve().parent.parent / "data"
SEV_WEIGHT = {"low": 2, "medium": 5, "high": 10, "critical": 18}


@lru_cache(maxsize=1)
def load_rules() -> dict:
    return yaml.safe_load((DATA / "rules.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_refs() -> dict:
    return yaml.safe_load((DATA / "ref_map.yaml").read_text(encoding="utf-8"))


def _finding(fid: str, evidence: dict | None = None, source: str = "detected") -> Finding:
    meta = load_rules()["findings"][fid]
    return Finding(id=fid, title=meta["title"], title_ar=meta.get("title_ar", ""), severity=meta["severity"],
                   evidence=evidence or {}, source=source, jurisdictions=meta["jurisdictions"],
                   refs=meta["refs"], fix_effort=meta.get("effort", "medium"))


# ---------------------------------------------------------------- applicability
def applicability(p: CompanyProfile, hosting_country: str | None) -> list[Applicability]:
    R = load_rules()
    eu = set(R["eu_countries"])
    sensitive = sorted(set(p.data_types) & set(R["sensitive_data_types"]))
    declared = p.is_critical_sector or p.is_government
    likely = (not declared) and p.sector in R["likely_critical_sectors"]
    critical = declared or likely
    eu_users = sorted(set(p.user_countries) & eu)
    eu_scope = bool(eu_users) or p.expanding_to_eu

    if declared:
        ncsc_en = "You are a government entity or in a critical sector, which the NCSC National Cybersecurity Framework covers."
        ncsc_ar = "أنتم جهة حكومية أو ضمن القطاعات الحيوية التي يشملها الإطار الوطني للأمن السيبراني."
    elif likely:
        ncsc_en = (f"Your sector ({p.sector}) is commonly treated as critical. The NCSC has not published its full sector list, "
                   "so confirm with the NCSC whether you are in scope.")
        ncsc_ar = (f"قطاعكم ({p.sector}) يُعامل عادةً كقطاع حيوي. لم ينشر المركز الوطني للأمن السيبراني قائمة القطاعات كاملة، "
                   "لذا تأكدوا من المركز إن كنتم مشمولين.")
    else:
        ncsc_en = "The NCSC framework currently covers government and critical-sector institutions; for you it is recommended, not mandatory."
        ncsc_ar = "يشمل الإطار الوطني حالياً الجهات الحكومية ومؤسسات القطاعات الحيوية؛ وهو بالنسبة لكم موصى به دون إلزام."

    out = [
        Applicability(framework="PDPL", applies=True, confidence="high",
                      reason="You process personal data of people in Jordan; Law No. 24 of 2023 applies to all such processing.",
                      reason_ar="تعالجون بيانات شخصية لأشخاص في الأردن، وقانون حماية البيانات الشخصية رقم 24 لسنة 2023 ينطبق على هذه المعالجة."),
        Applicability(framework="NCSC", applies=critical, confidence="high" if declared else "medium" if likely else "high",
                      reason=ncsc_en, reason_ar=ncsc_ar),
        Applicability(framework="GDPR", applies=eu_scope, confidence="high" if eu_users else "medium",
                      reason=(f"You serve users in the EU ({', '.join(eu_users)})." if eu_users else
                              "You plan to expand to the EU; GDPR will apply once you offer services to people there." if p.expanding_to_eu else
                              "No EU users and no EU expansion declared."),
                      reason_ar=(f"لديكم مستخدمون في الاتحاد الأوروبي ({', '.join(eu_users)})." if eu_users else
                                 "تخططون للتوسع إلى أوروبا؛ ستنطبق اللائحة GDPR عند تقديم خدماتكم هناك." if p.expanding_to_eu else
                                 "لا يوجد مستخدمون أوروبيون ولا خطة توسع معلنة.")),
        Applicability(framework="ISO27001", applies=eu_scope or critical, confidence="low",
                      reason="ISO 27001 is voluntary, but EU clients and critical-sector regulators commonly expect it.",
                      reason_ar="معيار ISO 27001 اختياري، لكن العملاء الأوروبيين والجهات الرقابية في القطاعات الحيوية يتوقعونه عادةً."),
    ]
    if sensitive:
        out[0].reason += f" You also process sensitive data ({', '.join(sensitive)})."
        out[0].reason_ar += " كما تعالجون بيانات حساسة."
    return out


# ---------------------------------------------------------------- evaluation
def evaluate(p: CompanyProfile, s: ScanResult, confirmed: dict | None = None) -> Report:
    """confirmed: facts the user corrected, e.g. {"hosting_country": "JO"} — they override detection."""
    confirmed = confirmed or {}
    R = load_rules()
    eu = set(R["eu_countries"])
    f: list[Finding] = []
    h, infra = s.headers or {}, s.infra or {}

    # --- transport security
    if not s.https.get("local_test"):
        if not s.https.get("https_ok"):
            f.append(_finding("NO_HTTPS", {"error": s.https.get("error")}))
        elif s.https.get("http_redirects_to_https") is False:
            f.append(_finding("HTTP_NOT_REDIRECTED", {"http_final_url": s.https.get("final_url")}))
    elif not s.https.get("https_ok"):
        f.append(_finding("NO_HTTPS", {"note": "demo site served over plain HTTP"}))

    if h and not h.get("hsts"):
        f.append(_finding("MISSING_HSTS", {"header": "Strict-Transport-Security"}))
    if h and not h.get("csp"):
        f.append(_finding("MISSING_CSP", {"header": "Content-Security-Policy"}))
    if h and not h.get("x_frame_options") and not h.get("frame_ancestors"):
        f.append(_finding("MISSING_XFO", {"header": "X-Frame-Options"}))
    leaked = [v for v in (h.get("server"), h.get("x_powered_by")) if v and any(c.isdigit() for c in v)]
    if leaked:
        f.append(_finding("SERVER_VERSION_DISCLOSED", {"values": leaked}))

    tls = s.tls or {}
    if tls.get("accepts_legacy"):
        f.append(_finding("WEAK_TLS", {"accepted": tls["accepts_legacy"]}))
    if isinstance(tls.get("cert_days_left"), int) and tls["cert_days_left"] < 21:
        f.append(_finding("CERT_EXPIRING", {"days_left": tls["cert_days_left"], "expires": tls.get("cert_expires")}))

    # --- cookies, trackers, consent
    tracking = [c["name"] for c in s.cookies if c.get("tracking")]
    trackers = infra.get("trackers", {})
    if tracking or (trackers and not s.consent_banner):
        f.append(_finding("COOKIE_BEFORE_CONSENT", {"tracking_cookies": tracking, "trackers_loaded_on_first_visit": sorted(trackers.values())}))
    # Session/app cookies need Secure + HttpOnly + SameSite; analytics cookies are JS-readable by design.
    weak = [c["name"] for c in s.cookies
            if (not c.get("secure")) or (not c.get("samesite")) or (not c.get("httponly") and not c.get("tracking"))]
    if weak:
        f.append(_finding("INSECURE_COOKIE_FLAGS", {"cookies": weak}))
    if trackers:
        f.append(_finding("THIRD_PARTY_TRACKERS", {"trackers": trackers, "locations": infra.get("tracker_locations", [])}))
    if not s.consent_banner and (trackers or s.cookies):
        f.append(_finding("NO_CONSENT_BANNER"))

    # --- transparency
    pp = s.privacy_policy or {}
    if not pp.get("found"):
        f.append(_finding("NO_PRIVACY_POLICY", {"searched_on": s.final_url}))
    else:
        analysis = pp.get("analysis") or {}          # filled by core.ai.analyze_privacy_policy (open LLM)
        dpo_needed = bool(set(p.data_types) & set(R["dpo_trigger_data_types"])) or p.processing_is_core_activity
        important = [m for m in analysis.get("missing", []) if m != "dpo_contact" or dpo_needed]
        if important:
            f.append(_finding("PRIVACY_POLICY_INCOMPLETE",
                              {"missing": important, "url": pp.get("url"), "analysed_by": analysis.get("generated_by")}))
        if not pp.get("has_arabic"):
            f.append(_finding("NO_ARABIC_PRIVACY_NOTICE", {"url": pp.get("url")}))

    # --- forms
    pii_forms = [x for x in s.forms if x.get("pii_fields")]
    if any(x.get("over_http") for x in pii_forms):
        f.append(_finding("FORM_OVER_HTTP", {"forms": [x["action"] for x in pii_forms if x["over_http"]]}))
    if pii_forms:
        f.append(_finding("FORM_COLLECTS_PII", {"fields": sorted({fld for x in pii_forms for fld in x["pii_fields"]})}))

    # --- data location (user-confirmed beats detected beats declared)
    if "hosting_country" in confirmed:
        hosting, h_src = confirmed["hosting_country"], "user_confirmed"
    elif infra.get("hosting_country"):
        hosting, h_src = infra["hosting_country"], "detected"
    else:
        hosting, h_src = p.hosting_country, "profile"
    if infra.get("origin_hidden") and "hosting_country" not in confirmed:
        f.append(_finding("ORIGIN_HIDDEN_BY_CDN", {"cdn": infra.get("cdn")}))
    if hosting and hosting != "JO":
        f.append(_finding("DATA_HOSTED_OUTSIDE_JO",
                          {"hosting_country": hosting, "cloud": infra.get("cloud"), "basis": h_src}, source=h_src))

    eu_users = sorted(set(p.user_countries) & eu)
    if (eu_users or p.expanding_to_eu) and hosting not in eu:
        f.append(_finding("EU_TRANSFER_TO_JORDAN", {"eu_users": eu_users or ["planned"], "hosting_country": hosting or "unknown"}, source="profile"))
        f.append(_finding("EU_REPRESENTATIVE_REQUIRED", {"reason": "controller not established in the EU"}, source="profile"))

    # --- email security
    dns_ = infra.get("dns") or {}
    if dns_ and not infra.get("spf"):
        f.append(_finding("NO_SPF"))
    if dns_ and not infra.get("dmarc"):
        f.append(_finding("NO_DMARC"))

    # --- organisational obligations from the profile
    sensitive = set(p.data_types) & set(R["sensitive_data_types"])
    dpo_types = set(p.data_types) & set(R["dpo_trigger_data_types"])
    abroad = bool(hosting and hosting != "JO")
    if dpo_types or p.processing_is_core_activity or abroad:            # PDPL Art. 11(A)(1)–(5)
        reasons = (["Art. 11(A)(1) processing is the core activity"] if p.processing_is_core_activity else []) + \
                  (["Art. 11(A)(2) sensitive data"] if sensitive else []) + \
                  (["Art. 11(A)(3) data of persons lacking legal capacity"] if "children" in dpo_types else []) + \
                  (["Art. 11(A)(4) financial data"] if "financial" in dpo_types else []) + \
                  (["Art. 11(A)(5) databases transferred outside the Kingdom"] if abroad else [])
        f.append(_finding("DPO_REQUIRED", {"triggers": reasons, "sensitive": sorted(sensitive)}, source="profile"))
    if (eu_users or p.expanding_to_eu) and (sensitive or p.processing_is_core_activity):
        f.append(_finding("GDPR_DPO_REQUIRED", {"sensitive": sorted(sensitive)}, source="profile"))
        f.append(_finding("DPIA_REQUIRED", {"sensitive": sorted(sensitive)}, source="profile"))
    if p.is_critical_sector or p.is_government or p.sector in R["likely_critical_sectors"]:
        f.append(_finding("NCSC_FRAMEWORK_APPLIES", {"sector": p.sector, "declared_by_you": p.is_critical_sector or p.is_government},
                          source="profile"))
    f.append(_finding("BREACH_PROCESS", {"notify_people": "within 24 hours (PDPL Art. 20(A)(1))",
                                         "notify_unit": "within 72 hours (PDPL Art. 20(A)(2))",
                                         "fines": "up to 500 JD/day, capped at 3% of annual revenue (Art. 21)"}, source="profile"))

    appl = applicability(p, hosting)
    active = {a.framework for a in appl if a.applies}
    if "GDPR" not in active:
        f = [x for x in f if x.jurisdictions != ["EU"]]

    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    f.sort(key=lambda x: (sev_order[x.severity], x.id))
    # Technical score: only detected issues count (profile obligations are to-dos, not failures).
    penalty = sum(SEV_WEIGHT[x.severity] for x in f if x.source != "profile")
    score = max(5, 100 - penalty // 2)
    return Report(profile=p, applicability=appl, findings=f, score=score)


def ref_label(ref: str, lang: str = "en") -> str:
    m = load_refs().get(ref, {})
    label = m.get("label_ar" if lang == "ar" else "label", ref)
    art = m.get("article")
    if art:
        return f"{label} [{art}]"
    return f"{label} [{'المادة قيد التحقق' if lang == 'ar' else 'article to be confirmed'}]"
