"""Download the official legal texts into data/laws/, then run:  python -m core.rag ingest

    python scripts/get_laws.py

Sources (checked 2026-10-24):
  PDPL_en.pdf  — official English translation published by MoDEE
  PDPL_ar.txt  — Arabic text of Law No. 24 of 2023 (transcription on jordan-lawyer.com; check against the Official Gazette)
  GDPR_en.pdf  — Regulation (EU) 2016/679, EUR-Lex
Not downloadable automatically — add by hand if you get them:
  NCSC_ar.pdf               — the NCSC National Cybersecurity Framework is not publicly posted; ask the NCSC
  CYBERSECURITY_LAW_ar.pdf  — Cybersecurity Law No. 16 of 2019 (Official Gazette / NCSC website)
"""
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parent.parent / "data" / "laws"
UA = {"User-Agent": "Mozilla/5.0 (Mutabiq law downloader)"}

PDFS = {
    "PDPL_en.pdf": "https://www.modee.gov.jo/EBV4.0/Root_Storage/EN/1/PDP_Law_-_English_Version-_officail_translation.pdf",
    "GDPR_en.pdf": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32016R0679",
}
HTML = {
    "PDPL_ar.txt": "https://jordan-lawyer.com/2023/09/20/%d9%82%d8%a7%d9%86%d9%88%d9%86-%d8%ad%d9%85%d8%a7%d9%8a%d8%a9-"
                   "%d8%a7%d9%84%d8%a8%d9%8a%d8%a7%d9%86%d8%a7%d8%aa-%d8%a7%d9%84%d8%b4%d8%ae%d8%b5%d9%8a%d8%a9/",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in PDFS.items():
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            (OUT / name).write_bytes(r.content)
            print(f"OK   {name}  ({len(r.content) // 1024} KB)")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {name}: {e}  -> download it in a browser from {url} and save it as data/laws/{name}")
    for name, url in HTML.items():
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            body = soup.find("article") or soup.find("div", class_="entry-content") or soup.body
            text = body.get_text("\n", strip=True)
            start = text.find("المادة 1")
            text = text[start:] if start > 0 else text
            if "المادة 15" not in text:
                raise ValueError("page did not contain the expected articles")
            (OUT / name).write_text(text, encoding="utf-8")
            print(f"OK   {name}  ({len(text)} chars)")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {name}: {e}  -> copy the law's text from {url} into data/laws/{name}")
    print("\nNext:  python -m core.rag ingest")


if __name__ == "__main__":
    main()
