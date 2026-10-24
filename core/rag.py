"""Retrieval layer — owned by the teammate (AI + interface).

Sources:
  1. data/knowledge/curated.yaml   — our own short notes per topic, tagged by audience + language
  2. data/laws/*.pdf | *.txt        — official texts, split by article. Name files LAW_lang.ext:
        PDPL_ar.pdf  PDPL_en.pdf  NCSC_ar.pdf  CYBERSECURITY_LAW_ar.pdf  GDPR_en.pdf
Search = BM25 (always) + bge-m3 vectors via Ollama (when Ollama is running), merged with
reciprocal-rank fusion. bge-m3 is multilingual: an Arabic query finds English chunks and back.

Commands:
  python -m core.rag ingest           # build data/index/chunks.json (+ vectors if Ollama is up)
  python -m core.rag search "consent cookies" --lang ar --audience plain
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

import requests
import yaml
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "data" / "laws"
INDEX = ROOT / "data" / "index"
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "bge-m3"

ARTICLE_SPLIT = re.compile(r"(?=(?:^|\n)\s*(?:المادة\s*\(?\s*[\d٠-٩]+|Article\s*\(?\s*\d+)\b)")
ARTICLE_NUM = re.compile(r"(?:المادة\s*\(?\s*([\d٠-٩]+)|Article\s*\(?\s*(\d+))")
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
TOKEN = re.compile(r"[\w؀-ۿ]+", re.UNICODE)


def _tok(text: str) -> list[str]:
    return [t.lower() for t in TOKEN.findall(text)]


# Everyday words people type → the words the law uses. Helps BM25 (and costs nothing when vectors are on).
SYNONYMS = {
    ("host", "hosting", "hosted", "server", "servers", "cloud", "aws", "azure", "gcp", "frankfurt", "abroad",
     "استضافة", "سيرفر", "سيرفرات", "خوادم", "سحابة", "برا", "الخارج"): "transfer outside Kingdom نقل خارج المملكة",
    ("fine", "fines", "penalty", "penalties", "punish", "غرامة", "الغرامة", "غرامات", "عقوبة", "العقوبات"): "penalties fine العقوبات غرامة",
    ("breach", "hack", "hacked", "leak", "leaked", "اختراق", "تسريب", "انسرقت", "تهكير"): "breach notify الإخلال بأمن وسلامة البيانات",
    ("dpo", "officer", "مراقب", "المراقب", "مسؤول"): "data protection officer appoint المراقب تعيين",
    ("cookie", "cookies", "tracking", "analytics", "كوكيز", "تتبع"): "consent cookies موافقة",
    ("delete", "erase", "remove", "حذف", "امسح", "محو"): "erase rights حقوق محو",
}


def _expand(query: str) -> str:
    toks = set(_tok(query))
    extra = [v for keys, v in SYNONYMS.items() if toks & set(keys)]
    return query + " " + " ".join(extra)


# ------------------------------------------------------------------ ingest
def _read_law(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        import fitz  # PyMuPDF
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    return path.read_text(encoding="utf-8")


def chunk_law(path: Path) -> list[dict]:
    stem = path.stem                       # e.g. PDPL_ar
    law, _, lang = stem.rpartition("_")
    law, lang = (law or stem).upper(), (lang if lang in ("ar", "en") else "en")
    chunks = []
    for part in ARTICLE_SPLIT.split(_read_law(path)):
        part = part.strip()
        if len(part) < 40:
            continue
        m = ARTICLE_NUM.search(part[:80])
        num = (m.group(1) or m.group(2)).translate(AR_DIGITS) if m else None
        for i in range(0, len(part), 1800):      # very long articles → windows
            chunks.append({"id": f"{law}-{lang}-art{num or 'x'}-{i // 1800}", "law": law, "lang": lang,
                           "article": f"Art. {num}" if num else None, "audience": "legal",
                           "topic": None, "text": part[i:i + 1800], "source": path.name})
    return chunks


def curated_chunks() -> list[dict]:
    items = yaml.safe_load((ROOT / "data" / "knowledge" / "curated.yaml").read_text(encoding="utf-8"))
    return [{**c, "law": c["topic"].split(":")[0], "article": None, "source": "curated"} for c in items]


def embed(texts: list[str]) -> list[list[float]] | None:
    try:
        r = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED_MODEL, "input": texts}, timeout=120)
        r.raise_for_status()
        return r.json()["embeddings"]
    except Exception:  # noqa: BLE001 — Ollama not running → BM25 only
        return None


def ingest() -> dict:
    chunks = curated_chunks()
    for p in sorted(LAWS.glob("*")):
        if p.suffix.lower() in (".pdf", ".txt", ".md"):
            chunks += chunk_law(p)
    INDEX.mkdir(parents=True, exist_ok=True)
    vectors = []
    for i in range(0, len(chunks), 32):
        v = embed([c["text"] for c in chunks[i:i + 32]])
        if v is None:
            vectors = None
            break
        vectors += v
    (INDEX / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    if vectors:
        (INDEX / "vectors.json").write_text(json.dumps(vectors))
    elif (INDEX / "vectors.json").exists():
        (INDEX / "vectors.json").unlink()
    _load.cache_clear()
    return {"chunks": len(chunks), "vectors": bool(vectors),
            "laws": sorted({c["source"] for c in chunks if c["source"] != "curated"})}


# ------------------------------------------------------------------ search
@lru_cache(maxsize=1)
def _load():
    path = INDEX / "chunks.json"
    chunks = json.loads(path.read_text(encoding="utf-8")) if path.exists() else curated_chunks()
    vpath = INDEX / "vectors.json"
    vectors = json.loads(vpath.read_text()) if vpath.exists() else None
    bm25 = BM25Okapi([_tok(c["text"] + " " + (c.get("topic") or "")) for c in chunks])
    return chunks, vectors, bm25


def _cos(a, b):
    num = sum(x * y for x, y in zip(a, b))
    den = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return num / den if den else 0.0


def search(query: str, k: int = 5, laws: list[str] | None = None, audience: str | None = None,
           lang: str | None = None, topic: str | None = None) -> list[dict]:
    """Hybrid search. topic boosts chunks tagged with that ref; audience/lang boost, never hard-filter,
    so a legal citation is still found when the owner asks in Arabic."""
    chunks, vectors, bm25 = _load()
    allowed = [i for i, c in enumerate(chunks) if not laws or c["law"] in laws]
    if not allowed:
        return []

    bm = bm25.get_scores(_tok(_expand(query)))
    rank_bm = sorted(allowed, key=lambda i: -bm[i])
    ranks = [rank_bm]
    if vectors:
        qv = embed([query])
        if qv:
            sims = {i: _cos(qv[0], vectors[i]) for i in allowed}
            ranks.append(sorted(allowed, key=lambda i: -sims[i]))

    score = {i: 0.0 for i in allowed}
    for ranking in ranks:                                   # reciprocal-rank fusion
        for pos, i in enumerate(ranking):
            score[i] += 1 / (60 + pos)
    for i in allowed:
        c = chunks[i]
        if topic and c.get("topic") == topic:
            score[i] += 0.05
        if audience and c.get("audience") == audience:
            score[i] += 0.01
        if lang and c.get("lang") == lang:
            score[i] += 0.008
    best = sorted(allowed, key=lambda i: -score[i])[:k]
    return [{**chunks[i], "score": round(score[i], 4)} for i in best]


def context_for_finding(finding, role: str, lang: str, k_per_ref: int = 2) -> list[dict]:
    """Retrieve the passages that back one finding: for each of its refs, search by that ref's query."""
    from core.rules import load_refs
    audience = {"owner": "plain", "developer": "technical", "legal": "legal"}[role]
    refs, seen, out = load_refs(), set(), []
    for ref in finding.refs:
        law = ref.split(":")[0]
        q = refs.get(ref, {}).get("query", ref) + " " + finding.title
        for hit in search(q, k=k_per_ref, laws=[law], audience=audience, lang=lang, topic=ref):
            if hit["id"] not in seen:
                seen.add(hit["id"])
                out.append({**hit, "for_ref": ref})
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        print(ingest())
    elif len(sys.argv) > 2 and sys.argv[1] == "search":
        args = sys.argv[2:]
        lang = args[args.index("--lang") + 1] if "--lang" in args else None
        aud = args[args.index("--audience") + 1] if "--audience" in args else None
        for h in search(args[0], lang=lang, audience=aud):
            print(h["score"], h["id"], "|", h["text"][:120].replace("\n", " "))
    else:
        print(__doc__)
