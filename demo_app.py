"""Mutabiq demo: business law & governance initial screening (Jordan). No login.
Run: streamlit run demo_app.py   (app.py remains the full product)."""
from __future__ import annotations

import html

import streamlit as st

import legal_review as svc
from legal_models import BusinessProfile
from legal_chat_ui import render_legal_chat

st.set_page_config(page_title="Mutabiq Legal Review Demo", page_icon=None, layout="wide",
                   initial_sidebar_state="collapsed")

ss = st.session_state
ss.setdefault("lang", "en")
ss.setdefault("report", None)
ss.setdefault("error", None)
ss.setdefault("responses", {})
ss.setdefault("p_sector", "health")
ss.setdefault("p_emp", True)
ss.setdefault("p_cons", True)
ss.setdefault("p_eu", "unknown")

AR = ss.lang == "ar"
E = html.escape
L = "ar" if AR else "en"
DEMO_NAME = "Shifa Health"
DEMO_SITE = getattr(svc, "DEMO_TARGET", None) or getattr(svc, "DEMO_URL", None) or "Included Shifa Health demo website"

STATUSES = ("review_needed", "needs_confirmation", "evidence_found", "self_reported", "out_of_scope")
STATUS = {
    "en": {
        "evidence_found": ("Disclosure signal found", "The public website contains wording that relates to this obligation. This is not proof of compliance."),
        "review_needed": ("Review needed", "No disclosure signal was found, or the business reported a gap. This is not a proven violation."),
        "needs_confirmation": ("Needs confirmation", "Cannot be established from a public website, or applicability depends on facts we do not have."),
        "self_reported": ("Self-reported", "A control or applicability claim made by the business. Mutabiq has not independently verified it."),
        "out_of_scope": ("Not selected by profile", "Not selected based only on the demo business facts. This is not a definitive legal exclusion."),
    },
    "ar": {
        "evidence_found": ("وُجدت إشارة إفصاح", "يتضمن الموقع العام نصاً يتعلق بهذا الالتزام. هذا ليس دليلاً على الامتثال."),
        "review_needed": ("يحتاج مراجعة", "لم نجد إشارة إفصاح، أو أبلغت المنشأة عن فجوة. هذه ليست مخالفة مثبتة."),
        "needs_confirmation": ("يحتاج تأكيداً", "لا يمكن إثباته من موقع عام، أو أن الانطباق يعتمد على وقائع غير متوفرة."),
        "self_reported": ("مُبلغ ذاتياً", "إقرار من المنشأة بشأن الإجراء أو نطاق الانطباق؛ لم يتحقق مطابق منه مستقلاً."),
        "out_of_scope": ("خارج النطاق", "اعتُبر غير منطبق بناءً على ملف العمل الذي قدمته فقط."),
    },
}[L]
SCOLOR = {"evidence_found": "var(--teal)", "review_needed": "var(--terra)", "needs_confirmation": "var(--gold)",
          "self_reported": "var(--plum)", "out_of_scope": "var(--mute)"}

T = {
    "en": dict(
        demo="Demo workspace", fictional="Fictional business", screen="Initial screening",
        notlegal="Not legal advice",
        h1a="Which business laws", h1b="deserve your attention?",
        lede="Mutabiq reads the public pages of a business website, maps them to a curated set of Jordanian business and governance obligations, and tells you plainly what it found, what it could not see, and what to ask your team.",
        juris="Jurisdiction", jo="Jordan (only jurisdiction in this demo)", site="Website read",
        sitenote="Included fictional demo website only. Public pages are read; nothing is probed or attacked.",
        areas="Eight review areas", areas_note="A curated selection of business and governance obligations. Not every Jordanian law, and not exhaustive within each area.",
        facts="Business facts", facts_note="Optional. These change which obligations apply.",
        sector="Sector", sectors={"health": "Healthcare", "retail": "Retail", "finance": "Finance", "services": "Services"},
        emp="Has employees", cons="Sells to consumers",
        eu="EU activity", eu_help="An establishment in the EU, or deliberately offering goods or services to, or monitoring, people in the EU. 'Unknown' keeps GDPR as a question, not an assertion.",
        eus={"unknown": "Unknown", "yes": "Yes", "no": "No"},
        run="Run legal review", retry="Try again", err="The review could not complete.",
        how=["Read", "Map", "Ask"],
        howd=["Public pages of the demo site: policies, terms, contact and about pages.",
              "Deterministic matching against a curated catalogue of legal references. No AI decides what the law says.",
              "Anything a website cannot show, such as tax, payroll or board records, becomes a question for you."],
        running="Reading public pages and mapping obligations",
        statuses="What each status means", nosc="There is no overall compliance score. Counts below are a screening snapshot.",
        area="Area", status="Status", all="All", items="obligations", none="No obligations match these filters.",
        law="Law", ref="Reference", src="Official source", req="What the law expects", why="Why this status",
        ev="Evidence from the website", q="Question for your internal records", act="Suggested follow-up",
        conf="Your confirmation", ans={"unknown": "Not sure yet", "in_place": "In place", "gap": "Gap identified", "not_applicable": "Not applicable"},
        note="Note (required for any answer other than Not sure yet)", save="Save answer",
        noteneed="Add a short note to record this answer. Without it the item stays as needs confirmation.",
        saved="Answer saved. Self-reported answers are not verified by Mutabiq.",
        yournote="Your note", unverified="Self-reported, not verified",
        dl="Download HTML report", rescan="Run again", reset="Back to start",
        warn="Review notes", created="Reviewed", docs="Pages read",
        disclaim="Curated initial screening, not legal advice. Laws are amended and applicability depends on facts; confirm current requirements with qualified Jordanian counsel. Tax, HR and governance obligations cannot be verified from a website. AML and health licensing items are conditional questions, not automatic violations.",
        foot="Mutabiq demo. Shifa Health is fictional. Session-only: nothing is uploaded or stored.",
        lang="العربية", open="Open source"),
    "ar": dict(
        demo="مساحة تجريبية", fictional="منشأة وهمية", screen="فحص أولي",
        notlegal="ليست استشارة قانونية",
        h1a="أي قوانين الأعمال", h1b="تستحق انتباهك؟",
        lede="يقرأ مطابق الصفحات العامة لموقع المنشأة، ويربطها بمجموعة منتقاة من التزامات الأعمال والحوكمة في الأردن، ثم يخبرك بوضوح بما وجده وما لم يستطع رؤيته وما يجب أن تسأل فريقك عنه.",
        juris="الولاية القضائية", jo="الأردن (الولاية الوحيدة في هذا العرض)", site="الموقع المقروء",
        sitenote="الموقع التجريبي الوهمي المرفق فقط. تُقرأ الصفحات العامة دون أي فحص اختراق.",
        areas="ثمانية مجالات مراجعة", areas_note="مجموعة منتقاة من التزامات الأعمال والحوكمة. ليست كل القوانين الأردنية ولا شاملة داخل كل مجال.",
        facts="معلومات المنشأة", facts_note="اختيارية. تغيّر الالتزامات المنطبقة.",
        sector="القطاع", sectors={"health": "رعاية صحية", "retail": "تجزئة", "finance": "مالية", "services": "خدمات"},
        emp="لديها موظفون", cons="تبيع للمستهلكين",
        eu="نشاط في الاتحاد الأوروبي", eu_help="منشأة داخل الاتحاد الأوروبي، أو تقديم سلع أو خدمات بشكل مقصود لأشخاص فيه أو مراقبتهم. 'غير معروف' يبقي GDPR سؤالاً لا تأكيداً.",
        eus={"unknown": "غير معروف", "yes": "نعم", "no": "لا"},
        run="ابدأ المراجعة القانونية", retry="حاول مجدداً", err="تعذر إكمال المراجعة.",
        how=["القراءة", "الربط", "السؤال"],
        howd=["الصفحات العامة للموقع التجريبي: السياسات والشروط وصفحات التواصل والتعريف.",
              "مطابقة ثابتة مع فهرس منتقى من المراجع القانونية. لا يقرر الذكاء الاصطناعي ما يقوله القانون.",
              "ما لا يظهره الموقع، كالضرائب والرواتب وسجلات مجلس الإدارة، يتحول إلى سؤال لك."],
        running="قراءة الصفحات العامة وربط الالتزامات",
        statuses="معنى كل حالة", nosc="لا توجد درجة امتثال إجمالية. الأعداد أدناه لقطة فحص أولي.",
        area="المجال", status="الحالة", all="الكل", items="التزامات", none="لا توجد التزامات تطابق هذه المرشحات.",
        law="القانون", ref="المرجع", src="المصدر الرسمي", req="ما يتطلبه القانون", why="سبب هذه الحالة",
        ev="دليل من الموقع", q="سؤال لسجلاتك الداخلية", act="المتابعة المقترحة",
        conf="تأكيدك", ans={"unknown": "لست متأكداً بعد", "in_place": "قائم", "gap": "توجد فجوة", "not_applicable": "لا ينطبق"},
        note="ملاحظة (مطلوبة لأي إجابة غير 'لست متأكداً')", save="حفظ الإجابة",
        noteneed="أضف ملاحظة قصيرة لتسجيل هذه الإجابة. بدونها يبقى البند بحاجة إلى تأكيد.",
        saved="تم الحفظ. الإجابات المُبلغ عنها ذاتياً لم يتحقق منها مطابق.",
        yournote="ملاحظتك", unverified="مُبلغ ذاتياً، غير متحقق منه",
        dl="تنزيل التقرير HTML", rescan="أعد المراجعة", reset="العودة للبداية",
        warn="ملاحظات المراجعة", created="وقت المراجعة", docs="صفحات مقروءة",
        disclaim="فحص أولي منتقى وليس استشارة قانونية. تتغير القوانين ويعتمد الانطباق على الوقائع؛ تحقق من المتطلبات الحالية مع مستشار قانوني أردني مؤهل. لا يمكن التحقق من التزامات الضرائب والموارد البشرية والحوكمة من موقع إلكتروني. بنود مكافحة غسل الأموال وترخيص الصحة أسئلة مشروطة وليست مخالفات تلقائية.",
        foot="عرض مطابق التجريبي. شفاء هيلث منشأة وهمية. ضمن الجلسة فقط: لا يُرفع أو يُخزن شيء.",
        lang="English", open="فتح المصدر"),
}[L]

# ---------------------------------------------------------------- styles
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;600&family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap');
:root {{
  --sand:#F4EEE3; --paper:#FBF8F2; --ink:#14302B; --ink2:#3C5A54; --mute:#7A8783;
  --teal:#0F6E56; --terra:#C4532D; --gold:#B98A1F; --plum:#6B4E7A; --line:#E3D9C8;
  --disp:{"'IBM Plex Sans Arabic'" if AR else "'Fraunces'"}, serif;
  --body:{"'IBM Plex Sans Arabic'" if AR else "'Instrument Sans'"}, sans-serif;
}}
.stApp {{ background: var(--sand); color: var(--ink); font-family: var(--body); }}
.stApp::before {{ content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.35;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.08'/%3E%3C/svg%3E"); }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 1120px; padding-top: 1.6rem; padding-bottom: 4rem; }}
{'.block-container {direction: rtl; text-align: right;}' if AR else ''}
/* Do not style every span: Streamlit uses icon-font spans for expander arrows. */
.stApp p, .stApp li, .stApp label {{ font-family: var(--body); }}
.mq-top {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap; }}
.mq-brand {{ display:flex; align-items:center; gap:.7rem; }}
.mq-mark {{ width:38px; height:38px; border-radius:11px; background:var(--ink); display:grid; place-items:center;
  color:var(--gold); font-family:'Fraunces',serif; font-weight:800; font-size:1.25rem; transform:rotate(-6deg); }}
.mq-name {{ font-family:var(--disp); font-weight:700; font-size:1.35rem; letter-spacing:-.02em; }}
.mq-name small {{ font-family:'JetBrains Mono',monospace; font-size:.68rem; color:var(--mute); margin-inline-start:.5rem; letter-spacing:.06em; text-transform:uppercase; }}
.mq-pills {{ display:flex; gap:.4rem; flex-wrap:wrap; }}
.mq-pill {{ font-family:'JetBrains Mono',monospace; font-size:.68rem; letter-spacing:.05em; text-transform:uppercase;
  padding:.32rem .6rem; border-radius:99px; border:1px solid var(--line); background:var(--paper); color:var(--ink2); }}
.mq-pill.d {{ background:var(--ink); color:var(--sand); border-color:var(--ink); }}
.mq-pill.w {{ border-color:var(--terra); color:var(--terra); }}
.mq-hero {{ display:grid; grid-template-columns:1.25fr .9fr; gap:2.5rem; align-items:center; margin:2.4rem 0 1.2rem; }}
.mq-h1 {{ font-family:var(--disp); font-weight:800; font-size:clamp(2.2rem,5vw,4rem); line-height:1.03; letter-spacing:-.035em; margin:0; color:var(--ink); }}
.mq-h1 em {{ font-style:italic; font-weight:400; color:var(--teal); }}
.mq-lede {{ font-size:1.06rem; line-height:1.6; color:var(--ink2); max-width:35rem; margin-top:1.1rem; }}
.mq-card {{ background:var(--paper); border:1px solid var(--line); border-radius:22px; padding:1.3rem 1.5rem;
  box-shadow:0 1px 0 #fff inset, 0 24px 48px -32px rgba(20,48,43,.35); position:relative; overflow:hidden; }}
.mq-lbl {{ font-family:'JetBrains Mono',monospace; font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; color:var(--mute); }}
.mq-org {{ font-family:var(--disp); font-size:1.7rem; font-weight:700; margin:.2rem 0 .6rem; }}
.mq-row {{ display:flex; justify-content:space-between; gap:1rem; border-top:1px dashed var(--line); padding:.55rem 0; font-size:.88rem; color:var(--ink2); }}
.mq-row b {{ color:var(--ink); font-weight:600; text-align:end; }}
.mq-arch {{ position:absolute; inset-inline-end:-40px; top:-40px; width:150px; height:150px; border-radius:50%; border:18px solid var(--gold); opacity:.16; }}
.mq-areas {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.5rem; margin:.6rem 0; }}
.mq-areas div {{ border:1px solid var(--line); background:var(--paper); border-radius:12px; padding:.6rem .75rem; font-size:.88rem; }}
.mq-areas i {{ font-style:normal; font-family:'JetBrains Mono',monospace; font-size:.68rem; color:var(--terra); display:block; }}
.mq-how {{ display:grid; grid-template-columns:repeat(3,1fr); margin:2rem 0 .5rem; border-top:2px solid var(--ink); }}
.mq-how div {{ padding:1rem 1.2rem 0 0; }}
.mq-how .n {{ font-family:'JetBrains Mono',monospace; color:var(--terra); font-size:.75rem; }}
.mq-how h4 {{ font-family:var(--disp); font-size:1.2rem; margin:.25rem 0 .3rem; color:var(--ink); }}
.mq-how p {{ color:var(--ink2); font-size:.92rem; line-height:1.5; margin:0; }}
div.stButton > button, div.stDownloadButton > button, div.stFormSubmitButton > button {{ border-radius:99px; font-family:var(--body); font-weight:600;
  border:1px solid var(--ink); background:transparent; color:var(--ink); transition:transform .15s ease; }}
div.stButton > button:hover, div.stDownloadButton > button:hover {{ transform:translateY(-1px); border-color:var(--teal); color:var(--teal); }}
div.stButton > button[kind="primary"] {{ background:var(--terra); border-color:var(--terra); color:#FFF8F0; font-size:1.02rem; padding:.75rem 1.8rem; }}
div.stButton > button[kind="primary"]:hover {{ background:#A9441F; color:#FFF8F0; border-color:#A9441F; }}
@keyframes rise {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:none; }} }}
.mq-rise {{ animation: rise .5s ease both; }}
.mq-sec {{ font-family:var(--disp); font-size:1.45rem; font-weight:700; margin:2rem 0 .7rem; letter-spacing:-.02em; }}
.mq-tally {{ display:grid; grid-template-columns:repeat(5,1fr); gap:.6rem; }}
.mq-tally div {{ border-radius:16px; padding:.85rem 1rem; background:var(--paper); border:1px solid var(--line); border-top:4px solid var(--c); }}
.mq-tally .v {{ font-family:'Fraunces',serif; font-size:2rem; font-weight:800; color:var(--c); line-height:1; }}
.mq-tally .k {{ font-weight:600; font-size:.88rem; margin:.3rem 0 .2rem; }}
.mq-tally p {{ font-size:.78rem; color:var(--ink2); line-height:1.4; margin:0; }}
.mq-badge {{ display:inline-block; font-family:'JetBrains Mono',monospace; font-size:.66rem; text-transform:uppercase; letter-spacing:.05em;
  padding:.2rem .5rem; border-radius:6px; color:#FFF8F0; }}
div[data-testid="stExpander"] {{ border:1px solid var(--line); border-radius:16px; background:var(--paper); margin-bottom:.5rem; overflow:hidden; }}
div[data-testid="stExpander"] details {{ border:0; }}
div[data-testid="stExpander"] summary p {{ font-weight:600; font-size:.97rem; }}
.mq-h {{ font-family:'JetBrains Mono',monospace; font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; color:var(--terra); margin:.9rem 0 .3rem; }}
.mq-p {{ color:var(--ink2); line-height:1.55; margin:0; }}
.mq-law {{ display:grid; grid-template-columns:1fr 1fr; gap:.8rem; background:var(--sand); border-radius:12px; padding:.75rem .9rem; }}
.mq-law b {{ display:block; font-size:.92rem; }} .mq-law a {{ color:var(--teal); font-size:.85rem; word-break:break-all; }}
.mq-quote {{ border-inline-start:3px solid var(--teal); padding:.4rem .9rem; background:#EEF3EE; border-radius:0 10px 10px 0; font-style:italic; color:var(--ink); }}
.mq-qbox {{ border:1px dashed var(--ink2); border-radius:12px; padding:.7rem .9rem; font-weight:500; }}
.mq-self {{ border:1px solid var(--plum); color:var(--plum); border-radius:10px; padding:.5rem .8rem; font-size:.88rem; margin-top:.6rem; }}
.mq-warn {{ border-inline-start:4px solid var(--gold); background:var(--paper); padding:.9rem 1.1rem; border-radius:12px; font-size:.9rem; line-height:1.55; color:var(--ink2); }}
.mq-foot {{ margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line); font-size:.78rem; color:var(--mute); line-height:1.5; }}
@media (max-width: 900px) {{ .mq-tally {{ grid-template-columns:repeat(2,1fr); }} .mq-areas {{ grid-template-columns:repeat(2,1fr); }} }}
@media (max-width: 768px) {{
  .mq-hero, .mq-how, .mq-law {{ grid-template-columns:1fr; gap:1.2rem; }}
}}
</style>
""", unsafe_allow_html=True)


def H(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def tr(obj, attr: str) -> str:
    ar = getattr(obj, attr + "_ar", "") if AR else ""
    return ar or getattr(obj, attr, "") or ""


def area_name(cid: str) -> str:
    a = svc.AREAS.get(cid) or {}
    return a.get(L) or a.get("en") or cid


def badge(status: str) -> str:
    return f'<span class="mq-badge" style="background:{SCOLOR.get(status, "var(--mute)")}">{E(STATUS.get(status, (status,))[0])}</span>'


def safe_url(u: str) -> str:
    u = (u or "").strip()
    return E(u) if u.startswith(("https://", "http://")) else ""


def profile() -> BusinessProfile:
    return BusinessProfile(name=DEMO_NAME, jurisdiction="JO", sector=ss.p_sector, has_employees=bool(ss.p_emp),
                           serves_consumers=bool(ss.p_cons), eu_activity=ss.p_eu)


def reset() -> None:
    # Streamlit discards keys belonging to widgets hidden on the results page.
    # Restore the reviewed facts rather than silently reverting scope on rescan.
    if ss.report is not None:
        current = ss.report.profile
        ss.p_sector = current.sector
        ss.p_emp = current.has_employees
        ss.p_cons = current.serves_consumers
        ss.p_eu = current.eu_activity
    ss.report, ss.error, ss.responses = None, None, {}
    ss.pop("f_area", None)
    ss.pop("f_status", None)


# ---------------------------------------------------------------- top bar
c1, c2 = st.columns([5, 1], vertical_alignment="center")
with c1:
    H(f"""<div class="mq-top"><div class="mq-brand"><div class="mq-mark">{'م' if AR else 'M'}</div>
<div class="mq-name">{'مطابق' if AR else 'Mutabiq'}<small>{'Mutabiq' if AR else 'مطابق'}</small></div></div>
<div class="mq-pills"><span class="mq-pill d">{T['demo']}</span><span class="mq-pill">{T['screen']}</span>
<span class="mq-pill w">{T['notlegal']}</span></div></div>""")
with c2:
    if st.button(T["lang"], key="lang_toggle", use_container_width=True):
        ss.lang = "en" if AR else "ar"
        st.rerun()

areas_html = '<div class="mq-areas">' + "".join(
    f'<div><i>0{i}</i>{E(area_name(cid))}</div>' for i, cid in enumerate(svc.AREAS, 1)) + "</div>"

# ---------------------------------------------------------------- landing
if ss.report is None:
    H(f"""<div class="mq-hero mq-rise"><div>
<h1 class="mq-h1">{T['h1a']} <em>{T['h1b']}</em></h1><p class="mq-lede">{T['lede']}</p></div>
<div class="mq-card"><div class="mq-arch"></div><div class="mq-lbl">{T['fictional']}</div>
<div class="mq-org">{'شفاء هيلث' if AR else DEMO_NAME}</div>
<div class="mq-row"><span>{T['juris']}</span><b>{T['jo']}</b></div>
<div class="mq-row"><span>{T['site']}</span><b style="direction:ltr">{E(str(DEMO_SITE))}</b></div>
<div class="mq-row"><span>{T['sitenote']}</span></div></div></div>""")
    H(f'<div class="mq-sec">{T["areas"]}</div>{areas_html}<p class="mq-p" style="font-size:.86rem">{T["areas_note"]}</p>')

    H(f'<div class="mq-sec">{T["facts"]}</div><p class="mq-p" style="font-size:.9rem;margin-bottom:.6rem">{T["facts_note"]}</p>')
    f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1.3])
    with f1:
        st.selectbox(T["sector"], list(T["sectors"]), format_func=lambda k: T["sectors"][k], key="p_sector")
    with f2:
        st.toggle(T["emp"], key="p_emp")
    with f3:
        st.toggle(T["cons"], key="p_cons")
    with f4:
        st.radio(T["eu"], ["unknown", "yes", "no"], format_func=lambda k: T["eus"][k], key="p_eu",
                 horizontal=True, help=T["eu_help"])

    if ss.error:
        st.error(f"{T['err']}  \n{ss.error}")
    if st.button(T["retry"] if ss.error else T["run"], type="primary", key="run") or ss.pop("_rescan", False):
        with st.spinner(T["running"]):
            try:
                ss.report, ss.error, ss.responses = svc.run_legal_review(profile()), None, {}
            except Exception as e:  # noqa: BLE001
                ss.error = str(e)[:300] or type(e).__name__
        st.rerun()
    H('<div class="mq-how">' + "".join(
        f'<div><div class="n">0{i+1}</div><h4>{T["how"][i]}</h4><p>{T["howd"][i]}</p></div>' for i in range(3)) + "</div>")
    render_legal_chat(report=None, lang=L)
    H(f'<div class="mq-warn" style="margin-top:1.6rem">{T["disclaim"]}</div><div class="mq-foot">{T["foot"]}</div>')
    st.stop()

# ---------------------------------------------------------------- results
report = ss.report
counts = report.counts()
p = report.profile

H(f"""<div class="mq-card mq-rise" style="margin-top:1.4rem"><div class="mq-arch"></div>
<div class="mq-lbl">{T['fictional']} · {T['jo']}</div>
<div class="mq-org">{'شفاء هيلث' if AR else E(p.name)}</div>
<div class="mq-row"><span>{T['sector']}</span><b>{E(T['sectors'].get(p.sector, p.sector))}</b></div>
<div class="mq-row"><span>{T['emp']} · {T['cons']} · {T['eu']}</span><b>{T['eus']['yes'] if p.has_employees else T['eus']['no']} · {T['eus']['yes'] if p.serves_consumers else T['eus']['no']} · {E(T['eus'].get(p.eu_activity, p.eu_activity))}</b></div>
<div class="mq-row"><span>{T['created']} · {T['docs']}</span><b style="direction:ltr">{E(str(report.created_at))} · {len(report.documents)}</b></div></div>""")

a1, a2, a3, _ = st.columns([1.3, 1, 1, 1.5])
with a1:
    try:
        st.download_button(T["dl"], data=svc.export_legal_report(report, lang=L),
                           file_name=f"mutabiq-legal-review-{L}.html", mime="text/html", use_container_width=True)
    except Exception as e:  # noqa: BLE001
        st.caption(f"Export unavailable: {E(str(e))}")
with a2:
    if st.button(T["rescan"], use_container_width=True):
        reset(); ss["_rescan"] = True; st.rerun()
with a3:
    if st.button(T["reset"], use_container_width=True):
        reset(); st.rerun()

H(f'<div class="mq-sec">{T["statuses"]}</div><p class="mq-p" style="font-size:.88rem;margin-bottom:.7rem">{T["nosc"]}</p>'
  '<div class="mq-tally">' + "".join(
      f'<div style="--c:{SCOLOR[s]}"><div class="v">{counts.get(s, 0)}</div><div class="k">{E(STATUS[s][0])}</div><p>{E(STATUS[s][1])}</p></div>'
      for s in STATUSES) + "</div>")

if report.warnings:
    H(f'<div class="mq-warn" style="margin-top:1rem"><b>{T["warn"]}</b><br>' + "<br>".join(E(str(w)) for w in report.warnings) + "</div>")

render_legal_chat(report=report, lang=L)

H(f'<div class="mq-sec">{T["areas"]}</div>')
g1, g2 = st.columns(2)
with g1:
    sel_area = st.selectbox(T["area"], ["all"] + list(svc.AREAS),
                            format_func=lambda k: T["all"] if k == "all" else area_name(k), key="f_area")
with g2:
    sel_status = st.selectbox(T["status"], ["all"] + list(STATUSES),
                              format_func=lambda k: T["all"] if k == "all" else STATUS[k][0], key="f_status")

order = {s: i for i, s in enumerate(STATUSES)}
cat_order = {c: i for i, c in enumerate(svc.AREAS)}
shown = sorted([f for f in report.findings
                if (sel_area == "all" or f.check.category == sel_area) and (sel_status == "all" or f.status == sel_status)],
               key=lambda f: (cat_order.get(f.check.category, 99), order.get(f.status, 9)))
st.caption(f"{len(shown)} / {len(report.findings)} {T['items']}")
if not shown:
    H(f'<div class="mq-card" style="text-align:center"><p class="mq-p">{T["none"]}</p></div>')

for f in shown:
    c = f.check
    with st.expander(f"{STATUS.get(f.status, (f.status,))[0]}  ·  {area_name(c.category)}  ·  {tr(c, 'title')}"):
        H(f'<div style="margin-bottom:.6rem">{badge(f.status)}</div><p class="mq-p" style="font-size:.85rem">{E(STATUS.get(f.status, ("", ""))[1])}</p>')
        link = safe_url(c.source_url)
        H(f'<div class="mq-law" style="margin-top:.7rem"><div><div class="mq-lbl">{T["law"]}</div><b>{E(c.law)}</b></div>'
          f'<div><div class="mq-lbl">{T["ref"]}</div><b>{E(c.reference)}</b>'
          + (f'<a href="{link}" target="_blank" rel="noopener noreferrer">{T["src"]}: {link}</a>' if link else "") + "</div></div>")
        H(f'<div class="mq-h">{T["req"]}</div><p class="mq-p">{E(tr(c, "requirement"))}</p>')
        H(f'<div class="mq-h">{T["why"]}</div><p class="mq-p">{E(tr(f, "reason"))}</p>')
        if f.evidence:
            ev_link = safe_url(f.evidence_url)
            H(f'<div class="mq-h">{T["ev"]}</div><div class="mq-quote">{E(f.evidence)}</div>'
              + (f'<p style="font-size:.8rem;direction:ltr"><a href="{ev_link}" target="_blank" rel="noopener noreferrer">{ev_link}</a></p>' if ev_link else ""))
        H(f'<div class="mq-h">{T["act"]}</div><p class="mq-p">{E(tr(c, "action"))}</p>')
        H(f'<div class="mq-h">{T["q"]}</div><div class="mq-qbox">{E(tr(c, "question"))}</div>')
        prev = ss.responses.get(c.id, {})
        if f.note or (f.status == "self_reported"):
            H(f'<div class="mq-self"><b>{T["unverified"]}</b>' + (f'<br>{T["yournote"]}: {E(f.note)}' if f.note else "") + "</div>")
        if f.status != "out_of_scope" or prev:
            H(f'<div class="mq-h">{T["conf"]}</div>')
            with st.form(f"form_{c.id}", border=False):
                keys = list(T["ans"])
                ans = st.radio(T["conf"], keys, index=keys.index(prev.get("answer", "unknown")) if prev.get("answer") in keys else 0,
                               format_func=lambda k: T["ans"][k], horizontal=True, label_visibility="collapsed")
                note = st.text_area(T["note"], value=prev.get("note", ""), max_chars=500, height=80)
                if st.form_submit_button(T["save"]):
                    if ans != "unknown" and not note.strip():
                        st.warning(T["noteneed"])
                    else:
                        resp = dict(ss.responses)
                        resp[c.id] = {"answer": ans, "note": note.strip()}
                        try:
                            ss.report = svc.update_review(report, resp)
                            ss.responses = resp
                            st.toast(T["saved"])
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(E(str(e)[:300]))

H(f'<div class="mq-warn" style="margin-top:2rem">{T["disclaim"]}</div><div class="mq-foot">{T["foot"]}</div>')
