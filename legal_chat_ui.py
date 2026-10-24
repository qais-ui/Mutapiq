"""Session-only legal Q&A surface for the Mutabiq demo. Native Streamlit only; no unsafe HTML."""
from __future__ import annotations

import streamlit as st

MAX_HISTORY = 12
MAX_CHARS = 1500

TXT = {
    "en": dict(
        title="Ask about the law in scope",
        intro="Ask plain questions about the curated Jordanian business and governance obligations in this demo. GDPR is discussed only where EU activity may make it relevant.",
        scope="Scope: curated Jordanian obligations plus conditional GDPR—not legal advice or every law. AI helps select relevant checks; explanations quote the catalogue, not independently generated legal advice. Sources are not verified live. Do not enter confidential or personal data. Chat never changes your review. This session only. Local AI may take up to two minutes.",
        ai="Local AI explanation · verify before relying on it",
        catalogue="Curated catalogue answer · not a legal determination",
        with_report="Your current review results are shared with the assistant as context.",
        no_report="No review yet. Answers are general to the curated catalogue; run a review for business-specific context.",
        starters="Try a question",
        placeholder="Ask a question about Jordanian business obligations",
        clear="Clear chat", retry="Retry last question",
        thinking="Consulting the curated catalogue with the local assistant",
        sources="Sources", empty="No messages yet. Pick a starter or type a question below.",
        failed="The assistant could not answer. Nothing was fabricated; your question is kept so you can retry.",
        unavailable="Chat unavailable", you="You", bot="Mutabiq",
        q=["Which laws apply to a Jordanian health clinic website?",
           "When could GDPR apply to a business based in Jordan?",
           "What should a privacy notice contain under Jordanian law?"],
    ),
    "ar": dict(
        title="اسأل عن القوانين ضمن النطاق",
        intro="اطرح أسئلة مباشرة حول التزامات الأعمال والحوكمة الأردنية المنتقاة في هذا العرض. يُناقش GDPR فقط عندما قد يجعله النشاط في الاتحاد الأوروبي ذا صلة.",
        scope="النطاق: التزامات أردنية منتقاة وGDPR المشروط، وليس كل القوانين أو استشارة قانونية. يساعد الذكاء الاصطناعي في اختيار نقاط المراجعة، والإجابات من الفهرس نفسه. لا تُتحقق المصادر مباشرة. لا تُدخل بيانات سرية أو شخصية. لا يتغير تقريرك. المحادثة لهذه الجلسة فقط. قد يستغرق الرد دقيقتين.",
        ai="شرح بالذكاء الاصطناعي المحلي · تحقق منه قبل الاعتماد عليه",
        catalogue="إجابة من الفهرس المنتقى · ليست حكماً قانونياً",
        with_report="تُشارك نتائج مراجعتك الحالية مع المساعد كسياق.",
        no_report="لا توجد مراجعة بعد. الإجابات عامة على الفهرس المنتقى؛ شغّل مراجعة للحصول على سياق خاص بالمنشأة.",
        starters="جرّب سؤالاً",
        placeholder="اطرح سؤالاً عن التزامات الأعمال في الأردن",
        clear="مسح المحادثة", retry="أعد محاولة السؤال الأخير",
        thinking="مراجعة الفهرس المنتقى بواسطة المساعد المحلي",
        sources="المصادر", empty="لا توجد رسائل بعد. اختر سؤالاً مقترحاً أو اكتب سؤالك أدناه.",
        failed="تعذر على المساعد الإجابة. لم يتم اختلاق أي إجابة؛ سؤالك محفوظ لإعادة المحاولة.",
        unavailable="المحادثة غير متاحة", you="أنت", bot="مطابق",
        q=["ما القوانين التي تنطبق على موقع عيادة صحية أردنية؟",
           "متى قد ينطبق GDPR على منشأة في الأردن؟",
           "ماذا يجب أن يتضمن إشعار الخصوصية وفق القانون الأردني؟"],
    ),
}


def _safe_url(u) -> str:
    u = str(u or "").strip()
    return u if u.startswith(("https://", "http://")) else ""


def _md_escape(s) -> str:
    s = str(s or "")
    for ch in "\\`*_[]<>#|$~":
        s = s.replace(ch, "\\" + ch)
    return s


def _render_sources(sources, t) -> None:
    if not sources:
        return
    with st.expander(f"{t['sources']} ({len(sources)})"):
        for s in sources:
            if not isinstance(s, dict):
                continue
            title = _md_escape(s.get("title") or s.get("id") or "")
            ref = _md_escape(s.get("reference") or "")
            url = _safe_url(s.get("url"))
            line = f"**{title}**" + (f" · {ref}" if ref else "")
            if url:
                line += f"  \n[{_md_escape(url)}]({url.replace(')', '%29').replace(' ', '%20')})"
            st.markdown(line)


def _ask(question: str, report, lang: str, t) -> None:
    from legal_chat import ChatUnavailable, answer_question

    ss = st.session_state
    hist = [{"role": m["role"], "content": m["content"]} for m in ss.chat_messages][-MAX_HISTORY:]
    ss.chat_busy = True
    try:
        with st.spinner(t["thinking"]):
            res = answer_question(question, hist, report=report, lang=lang)
        msgs = ss.chat_messages + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": str(res.get("answer", "")),
             "sources": list(res.get("sources") or []), "mode": res.get("mode", "")},
        ]
        ss.chat_messages = msgs[-MAX_HISTORY:]
        ss.chat_error, ss.chat_pending = None, None
    except ChatUnavailable as e:
        ss.chat_error, ss.chat_pending = str(e) or t["failed"], question
    except ValueError as e:
        ss.chat_error, ss.chat_pending = str(e) or t["failed"], question
    except Exception:  # noqa: BLE001
        ss.chat_error, ss.chat_pending = t["failed"], question
    finally:
        ss.chat_busy = False


def render_legal_chat(report=None, lang: str = "en") -> None:
    t = TXT.get(lang, TXT["en"])
    ss = st.session_state
    ss.setdefault("chat_messages", [])
    ss.setdefault("chat_error", None)
    ss.setdefault("chat_pending", None)
    ss.setdefault("chat_busy", False)
    ss.chat_busy = False  # a fresh run means no call is in flight

    with st.expander(t["title"], expanded=bool(ss.chat_messages or ss.chat_error)):
        st.markdown(t["intro"])
        st.caption(t["scope"])
        st.caption(t["with_report"] if report is not None else t["no_report"])

        queued = ss.pop("_chat_queued", None)

        box = st.container(border=True)
        with box:
            if not ss.chat_messages and not queued:
                st.caption(t["empty"])
            for m in ss.chat_messages:
                with st.chat_message(m["role"], avatar=None):
                    st.text(m["content"])  # plain text: never interpreted as HTML/markdown
                    if m["role"] == "assistant":
                        st.caption(t["catalogue"] if m.get("mode") == "catalogue" else t["ai"])
                        _render_sources(m.get("sources"), t)

        if ss.chat_error:
            st.error(f"{t['unavailable']}: {ss.chat_error}\n\n{t['failed']}")
            if ss.chat_pending:
                st.caption(f"{t['you']}: {ss.chat_pending}")

        st.caption(t["starters"])
        cols = st.columns(len(t["q"]))
        for i, (c, q) in enumerate(zip(cols, t["q"])):
            with c:
                if st.button(q, key=f"chat_starter_{lang}_{i}", use_container_width=True, disabled=ss.chat_busy):
                    queued = q

        b1, b2, _ = st.columns([1, 1, 2])
        with b1:
            if ss.chat_pending and st.button(t["retry"], key="chat_retry", use_container_width=True):
                queued = ss.chat_pending
        with b2:
            if st.button(t["clear"], key="chat_clear", use_container_width=True,
                         disabled=not (ss.chat_messages or ss.chat_error)):
                ss.chat_messages, ss.chat_error, ss.chat_pending = [], None, None
                st.rerun()

        with st.form("chat_form", clear_on_submit=True, border=False):
            typed = st.text_area(t["placeholder"], max_chars=MAX_CHARS, height=90, key="chat_input")
            if st.form_submit_button(t["title"], disabled=ss.chat_busy) and typed.strip():
                queued = typed.strip()[:MAX_CHARS]

        if queued:
            with st.chat_message("user", avatar=None):
                st.text(queued)
            _ask(queued, report, lang, t)
            st.rerun()
