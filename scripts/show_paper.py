"""Показывает скачанную статью в терминале: метаданные и все фрагменты по порядку.

    python scripts/show_paper.py 2511.21631
    python scripts/show_paper.py 2511.21631 --urls     # перед каждым фрагментом ссылка на абзац в arXiv
    python scripts/show_paper.py 2511.21631 --open     # открыть HTML-версию из локального кэша в браузере

Нужны data/processed/papers.parquet (есть в репозитории) и chunks.jsonl с кэшем в data/raw
(появляются после `python scripts/collect.py fulltext`).
"""
from __future__ import annotations

import argparse
import gzip
import json
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "data/processed/papers.parquet"
CHUNKS = ROOT / "data/processed/chunks.jsonl"
RAW_HTML = ROOT / "data/raw/html"
FT_LOG = ROOT / "data/processed/fulltext_log.jsonl"


def load_chunks(arxiv_id: str) -> list[dict]:
    if not CHUNKS.exists():
        sys.exit(f"Нет {CHUNKS.relative_to(ROOT)}. Сначала: python scripts/collect.py fulltext")
    out = []
    with CHUNKS.open() as f:
        for line in f:
            if f'"{arxiv_id}"' not in line:  # быстрый отсев до разбора JSON
                continue
            c = json.loads(line)
            if c["arxiv_id"] == arxiv_id:
                out.append(c)
    return sorted(out, key=lambda c: c["order"])


def open_local_html(arxiv_id: str) -> None:
    path = RAW_HTML / f"{arxiv_id.replace('/', '_')}.html.gz"
    if not path.exists():
        sys.exit(f"Нет {path.relative_to(ROOT)}: у этой статьи нет HTML-версии или она не скачана.")
    tmp = Path(tempfile.mkdtemp()) / f"{arxiv_id.replace('/', '_')}.html"
    tmp.write_bytes(gzip.decompress(path.read_bytes()))
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.run([opener, str(tmp)], check=False)
    print(f"Открыто из кэша: {tmp}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arxiv_id", help="номер статьи, например 2511.21631")
    ap.add_argument("--urls", action="store_true", help="показывать ссылку на каждый фрагмент")
    ap.add_argument("--open", action="store_true", help="открыть локальную HTML-версию в браузере")
    args = ap.parse_args()

    if args.open:
        open_local_html(args.arxiv_id)
        return

    papers = pd.read_parquet(PAPERS)
    row = papers[papers.arxiv_id == args.arxiv_id]
    if row.empty:
        sys.exit(f"Статьи {args.arxiv_id} нет в корпусе (data/processed/papers.parquet).")
    p = row.iloc[0]
    authors = ", ".join(p.authors[:5]) + (" и др." if len(p.authors) > 5 else "")
    print(f"{p.title}\n{authors}\narXiv:{p.arxiv_id}, {p.published}, {p.primary_category}")
    cites = p.get("citation_count")
    if pd.notna(cites):
        print(f"Цитирований: {int(cites)}")
    print(p.abs_url, "\n")

    chunks = load_chunks(args.arxiv_id)
    if not chunks:
        sys.exit(no_text_reason(args.arxiv_id))

    section = None
    for c in chunks:
        if c["source"] == "pdf":  # у PDF нет разделов: группируем по страницам
            heading = f"Страница {c['url'].rsplit('=', 1)[-1]}"
        else:
            heading = c["section"] or "(без раздела)"
        if c["type"] != "abstract" and heading != section:
            section = heading
            print(f"\n## {heading}")
        label = {"abstract": "Аннотация", "table": "Таблица"}.get(c["type"])
        if args.urls:
            print(f"\n{c['url']}")
        print(f"[{label}] {c['text']}\n" if label else f"{c['text']}\n")
    print(f"--- фрагментов: {len(chunks)}")


def no_text_reason(arxiv_id: str) -> str:
    """Почему нет фрагментов: не скачано или у статьи вообще нет текста."""
    if FT_LOG.exists():
        for line in FT_LOG.open():
            r = json.loads(line)
            if r["arxiv_id"] == arxiv_id:
                if r["format"] == "none":
                    return "У статьи нет доступного текста: нет ни HTML, ни PDF (например, статью отозвали авторы)."
                break
        else:
            return "Для этой статьи полный текст не загружался: она не входит в 440 статей с полным текстом."
    return "Полный текст не скачан. Запустите: python scripts/collect.py fulltext"


if __name__ == "__main__":
    if hasattr(signal, "SIGPIPE"):  # не падать при `... | head`
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
