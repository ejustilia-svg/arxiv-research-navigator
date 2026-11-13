"""Метаданные статей из arXiv API (Atom) и лицензии из OAI-PMH."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import feedparser

from . import http

API = "https://export.arxiv.org/api/query"
OAI = "https://oaipmh.arxiv.org/oai"
PAGE = 200


def _date_clause(d_from: str, d_to: str) -> str:
    f = d_from.replace("-", "") + "0000"
    t = d_to.replace("-", "") + "2359"
    return f"submittedDate:[{f} TO {t}]"


def build_query(q: str, categories: list[str], d_from: str, d_to: str) -> str:
    cats = " OR ".join(f"cat:{c}" for c in categories)
    return f"({q}) AND ({cats}) AND {_date_clause(d_from, d_to)}"


def _strip_version(arxiv_url: str) -> tuple[str, int]:
    m = re.search(r"abs/(.+?)(v(\d+))?$", arxiv_url)
    return m.group(1), int(m.group(3) or 1)


def parse_entry(e) -> dict:
    pid, ver = _strip_version(e.id)
    return {
        "arxiv_id": pid,
        "version": ver,
        "title": " ".join(e.title.split()),
        "abstract": " ".join(e.summary.split()),
        "authors": [a.name for a in e.get("authors", [])],
        "published": e.published[:10],
        "updated": e.updated[:10],
        "primary_category": e.get("arxiv_primary_category", {}).get("term"),
        "categories": [t["term"] for t in e.get("tags", [])],
        "comment": e.get("arxiv_comment"),
        "journal_ref": e.get("arxiv_journal_ref"),
        "doi": e.get("arxiv_doi"),
        "abs_url": f"https://arxiv.org/abs/{pid}",
        "html_url": f"https://arxiv.org/html/{pid}",
        "pdf_url": f"https://arxiv.org/pdf/{pid}",
    }


def search(query: str, max_results: int) -> list[dict]:
    out: list[dict] = []
    for start in range(0, max_results, PAGE):
        # arXiv API иногда отдаёт пустую страницу посреди выдачи — повторяем запрос
        for _ in range(3):
            r = http.get(API, params={
                "search_query": query, "start": start, "max_results": PAGE,
                "sortBy": "submittedDate", "sortOrder": "descending",
            })
            feed = feedparser.parse(r.text)
            total = int(feed.feed.get("opensearch_totalresults", 0))
            if feed.entries or start >= total:
                break
        batch = [parse_entry(e) for e in feed.entries]
        out.extend(batch)
        if len(batch) < PAGE or start + PAGE >= total:
            break
    return out


_NS = {"o": "http://www.openarchives.org/OAI/2.0/", "a": "http://arxiv.org/OAI/arXiv/"}


def fetch_license(arxiv_id: str) -> str | None:
    r = http.get(OAI, params={"verb": "GetRecord", "metadataPrefix": "arXiv",
                              "identifier": f"oai:arXiv.org:{arxiv_id}"})
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return None
    el = root.find(".//a:license", _NS)
    return el.text.strip() if el is not None and el.text else None


def is_open_license(lic: str | None) -> bool:
    """CC-лицензии и public domain разрешают повторное использование текста; дефолтная
    arXiv nonexclusive-distrib — только чтение (храним локально, не распространяем)."""
    return bool(lic) and ("creativecommons.org" in lic)


__all__ = ["build_query", "search", "fetch_license", "is_open_license"]
