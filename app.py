"""Mutabiq (مطابق) — Streamlit UI.   Run:  streamlit run app.py

Logins after `python scripts/seed.py`:  admin / admin123  (Mutabiq team)   shifa / shifa123  (client)
"""
from __future__ import annotations

import json

import streamlit as st

from core import audit
from core.db import DB_PATH, connect, encrypt, init_db
from core.engagement import (active_engagements_for_client, check_login, create_client, create_engagement,
                             expire_old, list_engagements, set_status)
from core.ai import analyze_privacy_policy, ask, profile_from_text
from core.gate import authorize_scan
from core.infra import map_infra
from core.llm import MODEL, cached_explanation, draft_privacy_notice, explain, ollama_status, warm_up
from core.report import render_html, to_pdf
from core.rules import evaluate
from core.scanner import normalize_target, scan
from core.schemas import CompanyProfile
from core.verify import LOCAL_HOSTS

st.set_page_config(page_title="Mutabiq · مطابق", page_icon="🛡️", layout="wide")

if not DB_PATH.exists():
    init_db()
expire_old()

# ------------------------------------------------------------------ i18n
UI = {
    "en": {"app": "Mutabiq — compliance map for Jordanian companies", "login": "Sign in", "user": "Username",
           "pw": "Password", "bad_login": "Wrong username or password", "logout": "Sign out", "lang": "Language",
           "role": "Explain for", "roles": {"owner": "Business owner", "developer": "Developer / IT", "legal": "Legal / DPO"},
           "eng": "1 · Your engagement", "no_eng": "No active contract for your company. Contact the Mutabiq team.",
           "scope": "Authorised domains", "valid": "Valid", "token": "Ownership proof — publish this as a DNS TXT record "
           "(or at /.well-known/mutabiq.txt)", "intake": "2 · About your company", "name": "Company name",
           "sector": "Sector", "critical": "We are in an NCSC critical sector", "gov": "We are a government entity",
           "data": "Data you collect", "countries": "Where your users are (ISO codes)", "hosting": "Where your data is hosted (if known)",
           "eu": "We plan to expand to the EU", "core": "Handling personal data is our main business", "save": "Save profile",
           "scan": "3 · Scan", "target": "Domain to scan", "run": "Run authorised scan", "blocked": "Scan blocked",
           "allowed": "Authorisation passed", "results": "4 · Results", "score": "Technical score",
           "applies": "Which rules apply to you", "findings": "Findings", "evidence": "Evidence",
           "correct": "Correct a detected fact", "real_host": "Our data is actually hosted in (ISO code)",
           "apply": "Apply correction", "report": "5 · Report", "dl_pdf": "Download PDF", "dl_html": "Download HTML (print → PDF)",
           "draft": "Generate draft privacy notice", "admin": "Mutabiq admin", "new_eng": "Record a signed engagement",
           "audit": "Audit log", "chain": "Verify audit chain", "llm_off": "Ollama is not running — using template explanations",
           "fill_profile": "Save your company profile first.", "explaining": "Explaining findings",
           "describe": "Describe your company in your own words (Arabic, dialect or English)",
           "describe_ph": "e.g. We're a clinic booking app in Amman, patient records on AWS Frankfurt, some patients live in Germany, we want to open in Europe next year",
           "ai_fill": "Fill the profile with AI", "ai_notes": "The model was unsure about",
           "review": "Review the answers below, then save.", "pp_check": "Privacy policy check (open LLM)",
           "pp_missing": "Missing", "pp_present": "Covered", "ask": "Ask Mutabiq", "ask_ph": "e.g. Do we need a Data Protection Officer?",
           "ask_btn": "Ask", "no_answer": "The open model is offline — here are the most relevant passages:",
           "ai_badge": "Local open-weight AI", "sources": "Sources",
           "urgent": "Critical + high", "frameworks_on": "Rules that apply", "ai_checks": "Checked by the open model",
           "top5": "Fix these first", "tab_all": "All", "tab_jo": "Jordan (PDPL · NCSC)", "tab_eu": "Europe (GDPR · ISO)",
           "tab_todo": "Organisational to-dos", "sev": {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"},
           "explain_ai": "🧠 Explain with Qwen (≈20 s)", "ai_slow": "The model didn't answer in time — click again (the first answer after start-up is the slowest).",
           "applies_yes": "Applies", "applies_no": "Not now", "effort": "Fix effort", "subtitle":
           "Jordan PDPL · NCSC framework · GDPR / ISO 27001 when you expand — explained by a local open-weight model"},
    "ar": {"app": "مطابق — خريطة الامتثال للشركات الأردنية", "login": "تسجيل الدخول", "user": "اسم المستخدم",
           "pw": "كلمة المرور", "bad_login": "اسم المستخدم أو كلمة المرور غير صحيحة", "logout": "تسجيل الخروج", "lang": "اللغة",
           "role": "الشرح موجّه إلى", "roles": {"owner": "صاحب العمل", "developer": "المطوّر / تقنية المعلومات", "legal": "القانوني / مسؤول حماية البيانات"},
           "eng": "1 · اتفاقيتكم", "no_eng": "لا توجد اتفاقية سارية لشركتكم. تواصلوا مع فريق مطابق.",
           "scope": "النطاقات المصرّح بفحصها", "valid": "سارية", "token": "إثبات الملكية — أضيفوا هذه القيمة كسجل DNS TXT "
           "(أو في /.well-known/mutabiq.txt)", "intake": "2 · عن شركتكم", "name": "اسم الشركة", "sector": "القطاع",
           "critical": "نحن ضمن القطاعات الحيوية للمركز الوطني للأمن السيبراني", "gov": "نحن جهة حكومية",
           "data": "البيانات التي تجمعونها", "countries": "أماكن مستخدميكم (رموز الدول)", "hosting": "مكان استضافة البيانات (إن كان معروفاً)",
           "eu": "نخطط للتوسع إلى الاتحاد الأوروبي", "core": "معالجة البيانات الشخصية هي نشاطنا الأساسي", "save": "حفظ الملف",
           "scan": "3 · الفحص", "target": "النطاق المراد فحصه", "run": "تشغيل الفحص المصرّح به", "blocked": "تم منع الفحص",
           "allowed": "تم التحقق من التفويض", "results": "4 · النتائج", "score": "الدرجة التقنية",
           "applies": "الأنظمة التي تنطبق عليكم", "findings": "الملاحظات", "evidence": "الدليل",
           "correct": "تصحيح معلومة مكتشفة", "real_host": "بياناتنا مستضافة فعلياً في (رمز الدولة)",
           "apply": "تطبيق التصحيح", "report": "5 · التقرير", "dl_pdf": "تنزيل PDF", "dl_html": "تنزيل HTML (اطبعه إلى PDF)",
           "draft": "إنشاء مسودة إشعار الخصوصية", "admin": "إدارة مطابق", "new_eng": "تسجيل اتفاقية موقّعة",
           "audit": "سجل التدقيق", "chain": "التحقق من سلامة السجل", "llm_off": "Ollama غير مشغّل — يتم استخدام شروحات جاهزة",
           "fill_profile": "احفظوا ملف الشركة أولاً.", "explaining": "جارٍ شرح الملاحظات",
           "describe": "صِفوا شركتكم بكلماتكم (بالعربية أو اللهجة أو الإنجليزية)",
           "describe_ph": "مثال: احنا تطبيق حجز عيادات في عمّان، ملفات المرضى على AWS فرانكفورت، وفي مرضى ساكنين بألمانيا، وبدنا نتوسع لأوروبا السنة الجاية",
           "ai_fill": "تعبئة الملف بالذكاء الاصطناعي", "ai_notes": "لم يكن النموذج متأكداً من",
           "review": "راجعوا الإجابات أدناه ثم احفظوا.", "pp_check": "فحص سياسة الخصوصية (نموذج مفتوح المصدر)",
           "pp_missing": "ناقص", "pp_present": "موجود", "ask": "اسأل مطابق", "ask_ph": "مثال: هل يلزمنا تعيين مسؤول حماية بيانات؟",
           "ask_btn": "اسأل", "no_answer": "النموذج المفتوح غير مشغّل — هذه أكثر النصوص صلة:",
           "ai_badge": "ذكاء اصطناعي مفتوح المصدر يعمل محلياً", "sources": "المصادر",
           "urgent": "حرجة وعالية", "frameworks_on": "الأنظمة المنطبقة", "ai_checks": "فحصها النموذج المفتوح",
           "top5": "ابدأوا بهذه", "tab_all": "الكل", "tab_jo": "الأردن (حماية البيانات · المركز الوطني)", "tab_eu": "أوروبا (GDPR · ISO)",
           "tab_todo": "التزامات تنظيمية", "sev": {"critical": "حرجة", "high": "عالية", "medium": "متوسطة", "low": "منخفضة"},
           "explain_ai": "🧠 اشرح باستخدام Qwen (≈20 ثانية)", "ai_slow": "لم يُجب النموذج في الوقت المحدد — اضغطوا مرة أخرى (أول إجابة بعد التشغيل هي الأبطأ).",
           "applies_yes": "ينطبق", "applies_no": "ليس حالياً", "effort": "جهد الإصلاح", "subtitle":
           "قانون حماية البيانات الأردني · الإطار الوطني للأمن السيبراني · GDPR وISO 27001 عند التوسع — بشرح نموذج ذكاء اصطناعي مفتوح يعمل محلياً"},
}
CHECK_LABELS = {
    "en": {"authenticated": "Signed in as a client", "active_contract": "Active signed contract",
           "in_scope": "Domain is in the contract scope", "owner_verified": "Domain ownership verified",
           "scan_allowed": "Scan type allowed by contract"},
    "ar": {"authenticated": "مسجّل الدخول كعميل", "active_contract": "اتفاقية موقّعة وسارية",
           "in_scope": "النطاق ضمن نطاق الاتفاقية", "owner_verified": "تم التحقق من ملكية النطاق",
           "scan_allowed": "نوع الفحص مسموح بموجب الاتفاقية"},
}
SECTORS = ["health", "finance", "telecom", "energy", "government", "education", "ecommerce", "other"]
DATA_TYPES = ["basic", "health", "financial", "biometric", "children", "location"]

@st.cache_data(show_spinner=False, max_entries=12)
def cached_pdf(html: str) -> bytes | None:
    return to_pdf(html)


ss = st.session_state
ss.setdefault("lang", "en")
ss.setdefault("role", "owner")

with st.sidebar:
    ss.lang = st.radio("Language · اللغة", ["en", "ar"], format_func=lambda x: "English" if x == "en" else "العربية",
                       index=0 if ss.lang == "en" else 1, horizontal=True)
    T = UI[ss.lang]
    ss.role = st.selectbox(T["role"], ["owner", "developer", "legal"], format_func=lambda r: T["roles"][r],
                           index=["owner", "developer", "legal"].index(ss.role))
    status = ollama_status()
    if status["llm_ready"] and not st.session_state.get("_warmed"):
        st.session_state["_warmed"] = True
        import threading
        threading.Thread(target=warm_up, daemon=True).start()
    if status["llm_ready"]:
        st.success(f"{T['ai_badge']}\n\n`{MODEL}` · Apache-2.0  \n`bge-m3` · MIT", icon="🧠")
    else:
        st.warning(T["llm_off"], icon="🟠")
    if ss.get("user"):
        st.caption(f"👤 {ss.user['display_name']}")
        if st.button(T["logout"]):
            for k in list(ss.keys()):
                if k not in ("lang", "role"):
                    del ss[k]
            st.rerun()

T = UI[ss.lang]
if ss.lang == "ar":
    st.markdown("""<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600&display=swap" rel="stylesheet">
    <style>.main .block-container, [data-testid="stMarkdownContainer"], label, .stButton, h1, h2, h3, p, li
    {direction: rtl; text-align: right; font-family: 'IBM Plex Sans Arabic', sans-serif;}
    code, pre {direction: ltr; text-align: left; unicode-bidi: isolate;}</style>""", unsafe_allow_html=True)

st.title(T["app"])
st.caption(T["subtitle"])

# ------------------------------------------------------------------ login
if not ss.get("user"):
    with st.form("login"):
        u = st.text_input(T["user"])
        p = st.text_input(T["pw"], type="password")
        if st.form_submit_button(T["login"]):
            user = check_login(u, p)
            if user:
                ss.user = user
                audit.log("login", user["id"], details={"username": u})
                st.rerun()
            else:
                audit.log("login_failed", None, details={"username": u})
                st.error(T["bad_login"])
    st.stop()

user = ss.user


# ------------------------------------------------------------------ admin view
def admin_view():
    st.header(T["admin"])
    with st.expander(T["new_eng"], expanded=False):
        with st.form("new_eng"):
            c1, c2 = st.columns(2)
            legal = c1.text_input("Client legal name")
            cr = c2.text_input("Commercial registration no.")
            eng_id = c1.text_input("Engagement ID", "ENG-2026-015")
            domains = c2.text_input("Scope domains (comma separated)")
            vf = c1.date_input("Valid from")
            vt = c2.date_input("Valid to")
            sig = c1.text_input("Authorised signatory")
            sig_t = c2.text_input("Signatory title")
            letter = st.file_uploader("Signed authorisation letter (PDF)", type=["pdf"])
            cl_user = c1.text_input("Client login username")
            cl_pw = c2.text_input("Client login password", type="password")
            if st.form_submit_button("Create engagement"):
                from core.engagement import create_user
                path = None
                if letter:
                    path = f"db/contracts/{eng_id}.pdf"
                    (DB_PATH.parent / "contracts").mkdir(exist_ok=True)
                    (DB_PATH.parent / "contracts" / f"{eng_id}.pdf").write_bytes(letter.getvalue())
                cid = create_client(legal, cr)
                if cl_user and cl_pw:
                    create_user(cl_user, cl_pw, "client", cid, display_name=legal)
                e = create_engagement(eng_id, cid, [d.strip() for d in domains.split(",") if d.strip()],
                                      vf.isoformat(), vt.isoformat(), sig, sig_t, contract_file=path, admin_id=user["id"])
                st.success(f"Created {e['id']}. Send the client this token: {e['verify_token']}")

    for e in list_engagements():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{e['id']}** · {e['legal_name']}  \n{', '.join(e['scope'])}")
            c2.markdown(f"{e['valid_from']} → {e['valid_to']}  \nstatus: `{e['status']}`")
            if e["status"] == "active" and c3.button("Revoke", key=f"rev{e['id']}"):
                set_status(e["id"], "revoked", user["id"])
                st.rerun()

    st.subheader(T["audit"])
    if st.button(T["chain"]):
        res = audit.verify_chain()
        (st.success if res["ok"] else st.error)(json.dumps(res))
    st.dataframe([{k: r[k] for k in ("id", "ts", "action", "target", "engagement_id", "allowed", "details")}
                  for r in audit.entries(100)], use_container_width=True)


if user["role"] == "admin":
    admin_view()
    st.stop()

# ------------------------------------------------------------------ client view
engs = active_engagements_for_client(user["client_id"])
st.header(T["eng"])
if not engs:
    st.warning(T["no_eng"])
    st.stop()
eng = engs[0]
c1, c2 = st.columns(2)
c1.markdown(f"**{eng['id']}** · {eng['legal_name']}  \n{T['scope']}: `{', '.join(eng['scope'])}`")
c2.markdown(f"{T['valid']}: {eng['valid_from']} → {eng['valid_to']}")
st.caption(T["token"])
st.code(eng["verify_token"], language=None)

st.header(T["intake"])
desc = st.text_area(T["describe"], placeholder=T["describe_ph"], height=90)
if st.button(T["ai_fill"], disabled=not desc.strip()):
    with st.spinner(MODEL):
        prof_ai, meta = profile_from_text(desc, eng["scope"][0], eng["legal_name"])
    if prof_ai:
        ss.profile, ss.ai_notes = prof_ai, meta.get("notes", "")
        ss.pv = ss.get("pv", 0) + 1
        audit.log("ai_intake", user["id"], None, eng["id"], None, {"model": meta["generated_by"]})
        st.rerun()
    else:
        st.warning(T["ai_slow"] if status["llm_ready"] else T["llm_off"])
if ss.get("ai_notes"):
    st.info(f"{T['review']} {T['ai_notes']}: {ss.ai_notes}")
prof = ss.get("profile")
with st.form(f"intake{ss.get('pv', 0)}"):
    c1, c2 = st.columns(2)
    name = c1.text_input(T["name"], prof.name if prof else eng["legal_name"])
    sector = c2.selectbox(T["sector"], SECTORS, index=SECTORS.index(prof.sector) if prof else 0)
    data = c1.multiselect(T["data"], DATA_TYPES, default=prof.data_types if prof else ["basic"])
    countries = c2.text_input(T["countries"], ",".join(prof.user_countries) if prof else "JO")
    hosting = c1.text_input(T["hosting"], (prof.hosting_country or "") if prof else "")
    crit = c2.checkbox(T["critical"], prof.is_critical_sector if prof else False)
    gov = c2.checkbox(T["gov"], prof.is_government if prof else False)
    eu = c1.checkbox(T["eu"], prof.expanding_to_eu if prof else False)
    core_act = c1.checkbox(T["core"], prof.processing_is_core_activity if prof else False)
    if st.form_submit_button(T["save"]):
        ss.profile = CompanyProfile(name=name, domain=eng["scope"][0], sector=sector, data_types=data,
                                    user_countries=[x.strip().upper() for x in countries.split(",") if x.strip()],
                                    hosting_country=hosting.strip().upper() or None, is_critical_sector=crit,
                                    is_government=gov, expanding_to_eu=eu, processing_is_core_activity=core_act)
        ss.pop("report", None)
        st.rerun()

st.header(T["scan"])
c1, c2 = st.columns([3, 1])
target = c1.text_input(T["target"], eng["scope"][0], help="Try a domain outside your contract to see the gate block it.")
if c2.button(T["run"], type="primary", use_container_width=True):
    if not ss.get("profile"):
        st.warning(T["fill_profile"])
    else:
        gate = authorize_scan(user, target)
        for k, ok in gate.checks.items():
            st.markdown(f"{'✅' if ok else '❌'} {CHECK_LABELS[ss.lang][k]}")
        if not gate.allowed:
            st.error(T["blocked"])
            ss.pop("report", None)
        else:
            st.success(f"{T['allowed']} · {gate.verify_method}")
            host = normalize_target(target)
            local = host in LOCAL_HOSTS
            with st.spinner("Scanning…"):
                res = scan(host, base_url="http://127.0.0.1:5001" if local else None)
                if not local:
                    res.infra.update(map_infra(host, res.headers.get("raw"), list(res.infra.get("trackers", {}).keys())))
            if res.privacy_policy.get("found"):
                with st.spinner(f"{T['pp_check']} · {MODEL}"):
                    res.privacy_policy["analysis"] = analyze_privacy_policy(res.privacy_policy.get("text_excerpt", ""))
            ss.profile = ss.profile.model_copy(update={"domain": host})
            ss.scan, ss.confirmed, ss.engagement_id = res, {}, gate.engagement["id"]
            ss.explanations, ss.saved_scan = {}, False

if ss.get("scan") and ss.get("profile"):
    report = evaluate(ss.profile, ss.scan, ss.confirmed)
    report.engagement_id = ss.engagement_id
    ss.report = report

    st.header(T["results"])

    # Instant: AI explanation from the cache (prewarm / earlier clicks), otherwise the template.
    # The model is only called when someone clicks "Explain with Qwen" on a finding (~20 s on a laptop GPU).
    key = (ss.role, ss.lang)
    ss.setdefault("explanations", {})
    ss.setdefault("ai_done", {})
    if key not in ss.explanations:
        ss.explanations[key] = {f.id: cached_explanation(f, ss.role, ss.lang) or explain(f, ss.role, ss.lang, use_llm=False)
                                for f in report.findings}
    exps = ss.explanations[key]
    for fid, ans in list(ss.ai_done.get(key, {}).items()):
        exps[fid] = ans

    detected = [f for f in report.findings if f.source != "profile"]
    todos = [f for f in report.findings if f.source == "profile"]
    urgent = [f for f in report.findings if f.severity in ("critical", "high")]
    ai_n = sum(1 for e in exps.values() if e.get("generated_by") not in (None, "template"))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(T["score"], f"{report.score}/100")
    m2.metric(T["urgent"], len(urgent))
    m3.metric(T["frameworks_on"], sum(a.applies for a in report.applicability))
    m4.metric(T["ai_checks"], f"{ai_n}/{len(report.findings)}")

    st.markdown(f"**{T['applies']}**")
    cols = st.columns(len(report.applicability))
    for col, a in zip(cols, report.applicability):
        with col.container(border=True):
            badge = f":red-background[{T['applies_yes']}]" if a.applies else f":gray-background[{T['applies_no']}]"
            st.markdown(f"**{a.framework}** &nbsp; {badge}")
            st.caption(a.reason_ar if ss.lang == "ar" else a.reason)

    SEV_COLOR = {"critical": "red", "high": "orange", "medium": "violet", "low": "blue"}

    def title_of(f):
        return f.title_ar if ss.lang == "ar" and f.title_ar else f.title

    if ss.role == "owner" and urgent:
        with st.container(border=True):
            st.markdown(f"**{T['top5']}**")
            for i, f in enumerate(urgent[:5], 1):
                ex = exps.get(f.id, {})
                first = (ex.get("what_to_do") or [""])[0]
                st.markdown(f"{i}. **{title_of(f)}** — {first}")

    def render_finding(f, where):
        ex = exps.get(f.id) or explain(f, ss.role, ss.lang)
        with st.expander(f"{T['sev'][f.severity]} · {title_of(f)}"):
            st.markdown(f":{SEV_COLOR[f.severity]}-background[{T['sev'][f.severity]}] &nbsp; "
                        f"{T['effort']}: **{f.fix_effort}** &nbsp; · &nbsp; {' / '.join(f.jurisdictions)}")
            if ex["summary"] and ex["summary"] != title_of(f):
                st.markdown(ex["summary"])
            st.markdown(ex["why_it_matters"])
            for step in ex["what_to_do"]:
                st.markdown(f"- {step}")
            st.caption(" · ".join(ex["citation_labels"]))
            if ss.role != "owner" and f.evidence:
                st.caption(f"{T['evidence']} ({f.source})")
                st.json(f.evidence, expanded=False)
            if ss.role == "legal":
                for s_ in ex["sources"][:3]:
                    st.caption(f"↳ {s_['source']} {s_['article'] or ''}: {s_['excerpt'][:240]}…")
            if ex.get("generated_by") == "template":
                if st.button(T["explain_ai"], key=f"ai_{where}_{f.id}_{ss.role}_{ss.lang}", disabled=not status["llm_ready"]):
                    with st.spinner(f"{MODEL} …"):
                        ans = explain(f, ss.role, ss.lang)
                    if ans.get("generated_by") == "template":
                        st.warning(T["ai_slow"])
                    else:
                        ss.ai_done.setdefault((ss.role, ss.lang), {})[f.id] = ans
                        st.rerun()
            else:
                st.caption(f"🧠 {ex.get('generated_by')}{' · cached' if ex.get('cached') else ''}")

    st.subheader(f"{T['findings']} ({len(report.findings)})")
    eu_on = any(a.applies for a in report.applicability if a.framework == "GDPR")
    tabs = st.tabs([f"{T['tab_all']} ({len(detected)})", T["tab_jo"]] + ([T["tab_eu"]] if eu_on else []) +
                   [f"{T['tab_todo']} ({len(todos)})"])
    with tabs[0]:
        for f in detected:
            render_finding(f, "all")
    with tabs[1]:
        for f in [x for x in report.findings if "JO" in x.jurisdictions]:
            render_finding(f, "jo")
    if eu_on:
        with tabs[2]:
            for f in [x for x in report.findings if "EU" in x.jurisdictions]:
                render_finding(f, "eu")
    with tabs[-1]:
        for f in todos:
            render_finding(f, "todo")

    with st.expander(T["correct"]):
        real = st.text_input(T["real_host"], ss.confirmed.get("hosting_country", ""))
        if st.button(T["apply"]):
            ss.confirmed = {**ss.confirmed, "hosting_country": real.strip().upper()} if real.strip() else {}
            ss.explanations = {}
            audit.log("fact_corrected", user["id"], ss.scan.target, ss.engagement_id, None, {"hosting_country": real})
            st.rerun()

    analysis = (ss.scan.privacy_policy or {}).get("analysis")
    if analysis and analysis.get("elements"):
        with st.expander(f"🧠 {T['pp_check']} — {analysis['generated_by']}", expanded=True):
            from core.ai import POLICY_ELEMENTS
            c1, c2 = st.columns(2)
            for i, (k, v) in enumerate(analysis["elements"].items()):
                label = POLICY_ELEMENTS[k][1 if ss.lang == "ar" else 0]
                (c1 if i % 2 == 0 else c2).markdown(
                    f"{'✅' if v['present'] else '❌'} {label}" + (f"  \n<small>“{v['quote']}”</small>" if v.get("quote") else ""),
                    unsafe_allow_html=True)

    st.header(T["ask"])
    q = st.text_input(T["ask_ph"], key="ask_q", label_visibility="collapsed", placeholder=T["ask_ph"])
    if st.button(T["ask_btn"]) and q.strip():
        laws = ["PDPL", "NCSC", "CYBERSECURITY_LAW"] + (["GDPR", "EPRIVACY", "ISO"] if any(
            a.applies for a in report.applicability if a.framework == "GDPR") else [])
        with st.spinner(MODEL):
            ss.qa = ask(q, ss.lang, laws)
        audit.log("ai_question", user["id"], None, ss.engagement_id, None, {"model": ss.qa.get("generated_by")})
    if ss.get("qa"):
        if ss.qa["answer"]:
            st.markdown(ss.qa["answer"])
        else:
            st.caption(T["no_answer"])
        with st.expander(T["sources"]):
            for src in ss.qa["sources"]:
                st.markdown(f"**[{src['n']}] {src['label']}**  \n{src['text'][:500]}")

    st.header(T["report"])
    draft = ss.get("privacy_draft", {}).get(ss.lang)
    if ss.role == "legal" and st.button(T["draft"]):
        with st.spinner("…"):
            ss.setdefault("privacy_draft", {})[ss.lang] = draft = draft_privacy_notice(ss.profile, report.findings, ss.lang)
    html = render_html(report, exps, ss.role, ss.lang, draft)
    pdf = cached_pdf(html)
    fname = f"mutabiq_{report.engagement_id}_{ss.role}_{ss.lang}"
    c1, c2 = st.columns(2)
    if pdf:
        if c1.download_button(T["dl_pdf"], pdf, f"{fname}.pdf", "application/pdf"):
            audit.log("report_downloaded", user["id"], ss.scan.target, ss.engagement_id, None, {"role": ss.role, "lang": ss.lang})
    c2.download_button(T["dl_html"], html, f"{fname}.html", "text/html")

    # Encrypted copy of the result for the engagement record (retention handled per contract)
    if not ss.get("saved_scan"):
        with connect() as c:
            c.execute("INSERT INTO scans (engagement_id, target, report_enc) VALUES (?,?,?)",
                      (ss.engagement_id, ss.scan.target, encrypt(report.model_dump_json())))
        ss.saved_scan = True

