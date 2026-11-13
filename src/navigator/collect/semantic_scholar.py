"""Обогащение метаданных из Semantic Scholar Graph API (batch-эндпоинт, до 500 id за запрос).

Без ключа API работает в общем пуле с жёстким rate limit (часто 429) — поэтому ретраи
с backoff. Ключ (бесплатный, по заявке) кладётся в переменную окружения S2_API_KEY.
"""
from __future__ import annotations

import os

from . import http

URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
FIELDS = ("externalIds,citationCount,influentialCitationCount,referenceCount,venue,"
          "publicationTypes,fieldsOfStudy,s2FieldsOfStudy,tldr,openAccessPdf")


def enrich(arxiv_ids: list[str], batch: int = 400) -> dict[str, dict]:
    headers = {"x-api-key": k} if (k := os.getenv("S2_API_KEY")) else {}
    out: dict[str, dict] = {}
    for i in range(0, len(arxiv_ids), batch):
        ids = arxiv_ids[i:i + batch]
        r = http.post(URL, params={"fields": FIELDS}, json={"ids": [f"ARXIV:{a}" for a in ids]},
                      headers=headers, host_delay=3.0, retries=8)
        r.raise_for_status()
        for aid, rec in zip(ids, r.json()):
            if not rec:
                continue
            out[aid] = {
                "s2_paper_id": rec.get("paperId"),
                "citation_count": rec.get("citationCount"),
                "influential_citation_count": rec.get("influentialCitationCount"),
                "reference_count": rec.get("referenceCount"),
                "venue": rec.get("venue") or None,
                "publication_types": rec.get("publicationTypes"),
                "s2_fields": sorted({f["category"] for f in rec.get("s2FieldsOfStudy") or []}),
                "tldr": (rec.get("tldr") or {}).get("text"),
                "open_access_pdf": (rec.get("openAccessPdf") or {}).get("url"),
            }
    return out
