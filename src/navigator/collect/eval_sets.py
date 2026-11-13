"""Внешние эталонные датасеты для оценки.

* QASPER (allenai/qasper) — вопросы по NLP-статьям с размеченными ответами и
  evidence-абзацами -> проверяем QA и то, что цитата указывает на верный фрагмент.
* ArxivDIGESTables (blnewman/arxivDIGESTables, Newman et al., 2024) — таблицы
  сравнения из обзорных статей arXiv + id статей-строк -> эталон для таблицы
  «метод / датасет / метрики».
"""
from __future__ import annotations

from pathlib import Path

from . import http

HF = "https://huggingface.co"
QASPER = {s: f"{HF}/api/datasets/allenai/qasper/parquet/qasper/{s}/0.parquet"
          for s in ("train", "validation", "test")}
DIGEST = {f: f"{HF}/datasets/blnewman/arxivDIGESTables/resolve/main/{f}"
          for f in ("papers.jsonl", "tables_dataset_viewer_only.jsonl")}


def download(dest: Path) -> list[Path]:
    paths = []
    for name, urls in (("qasper", QASPER), ("arxivdigestables", DIGEST)):
        d = dest / name
        d.mkdir(parents=True, exist_ok=True)
        for key, url in urls.items():
            p = d / (key if "." in key else f"{key}.parquet")
            if not p.exists():
                r = http.get(url, host_delay=0.5, allow_redirects=True, timeout=600)
                r.raise_for_status()
                p.write_bytes(r.content)
            paths.append(p)
    return paths
