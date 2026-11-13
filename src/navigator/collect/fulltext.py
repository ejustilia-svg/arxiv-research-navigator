"""Полные тексты: arXiv HTML (LaTeXML) -> чанки с якорями для цитирования.

Каждый абзац LaTeXML имеет стабильный id (например, ``S3.SS1.p2``), поэтому
цитата в ответе = ссылка ``https://arxiv.org/html/<id>#S3.SS1.p2``, которую
пользователь может открыть и проверить. Если HTML нет (старые/битые сборки),
падаем на PDF через PyMuPDF — там якорь = номер страницы.
"""
from __future__ import annotations

import re

import pymupdf
from bs4 import BeautifulSoup, Tag

from . import http


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section_title(sec: Tag) -> str:
    h = sec.find(re.compile(r"h[1-6]"), class_=re.compile("ltx_title"))
    return _clean(h.get_text(" ")) if h else ""


def _math_to_text(soup: BeautifulSoup) -> None:
    # формулы -> их LaTeX-alttext, чтобы не терять смысл и не тащить MathML-мусор
    for m in soup.find_all("math"):
        m.replace_with(f" ${m.get('alttext', '')}$ ")


def _table_to_text(fig: Tag) -> str:
    rows = []
    for tr in fig.find_all("tr"):
        cells = [_clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


MAX_CHARS = 1500  # длинные абзацы (доказательства, промпты в приложениях) режем на части с тем же якорем


def _split(text: str, limit: int = MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(sent) + 1 > limit:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {sent}".strip()
        while len(cur) > limit:  # «предложение» длиннее лимита (формулы, листинги)
            parts.append(cur[:limit])
            cur = cur[limit:]
    if cur:
        parts.append(cur)
    return parts


def parse_html(arxiv_id: str, html: str, abstract_fallback: str | None = None) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    _math_to_text(soup)
    for junk in soup.select(".ltx_bibliography, nav, header, footer, .ltx_page_footer"):
        junk.decompose()

    raw: list[dict] = []
    abstract = soup.select_one(".ltx_abstract")
    abs_text = (_clean(abstract.get_text(" ")).removeprefix("Abstract").strip() if abstract else "") or abstract_fallback
    if abs_text:
        raw.append(dict(type="abstract", section="Abstract", anchor="abstract", text=abs_text))

    for para in soup.select("div.ltx_para[id]"):
        # вложенные ltx_para (пункты списков, теоремы) уже входят в текст внешнего абзаца
        if para.find_parent("figure") or para.find_parent("div", class_="ltx_para"):
            continue
        sec = para.find_parent("section")
        text = _clean(para.get_text(" "))
        if len(text) < 40:
            continue
        raw.append(dict(type="paragraph", section=_section_title(sec) if sec else "",
                        anchor=para["id"], text=text))

    for fig in soup.select("figure.ltx_table[id]"):
        if fig.find_parent("figure", class_="ltx_table"):  # подтаблицы входят во внешнюю
            continue
        cap_el = fig.find("figcaption")
        cap = _clean(cap_el.get_text(" ")) if cap_el else ""
        body = _table_to_text(fig)
        text = "\n".join(x for x in (cap, body) if x)  # подпись в тексте -> находится поиском
        if not text:
            continue
        sec = fig.find_parent("section")
        raw.append(dict(type="table", section=_section_title(sec) if sec else "",
                        anchor=fig["id"], caption=cap, text=text,
                        table_is_image=not body))

    chunks: list[dict] = []
    base = f"https://arxiv.org/html/{arxiv_id}"
    for c in raw:
        pieces = _split(c["text"]) if c["type"] == "paragraph" else [c["text"]]  # таблицы и аннотацию не режем
        for k, piece in enumerate(pieces):
            suffix = f"~{k}" if len(pieces) > 1 else ""
            chunks.append({**c, "text": piece, "arxiv_id": arxiv_id,
                           "chunk_id": f"{arxiv_id}#{c['anchor']}{suffix}",
                           "url": f"{base}#{c['anchor']}" if c["anchor"] != "abstract"
                           else f"https://arxiv.org/abs/{arxiv_id}",
                           "source": "html"})
    for i, c in enumerate(chunks):
        c["order"] = i
    return chunks


def parse_pdf(arxiv_id: str, pdf_bytes: bytes) -> list[dict]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    chunks = []
    for pno, page in enumerate(doc, start=1):
        for bi, block in enumerate(page.get_text("blocks")):
            text = _clean(block[4])
            if len(text) < 40:
                continue
            pieces = _split(text)
            for k, piece in enumerate(pieces):
                suffix = f"~{k}" if len(pieces) > 1 else ""
                chunks.append(dict(type="paragraph", section="", anchor=f"p{pno}.b{bi}", text=piece,
                                   arxiv_id=arxiv_id, chunk_id=f"{arxiv_id}#p{pno}.b{bi}{suffix}",
                                   url=f"https://arxiv.org/pdf/{arxiv_id}#page={pno}", source="pdf"))
    for i, c in enumerate(chunks):
        c["order"] = i
    return chunks


def fetch(arxiv_id: str) -> tuple[str, bytes | str | None]:
    """Возвращает (формат, сырой контент). HTML приоритетнее PDF."""
    r = http.get(f"https://arxiv.org/html/{arxiv_id}")
    # если HTML-сборки нет, arXiv отдаёт 404 или страницу-заглушку без ltx_document
    if r.status_code == 200 and "ltx_document" in r.text:
        return "html", r.text
    r = http.get(f"https://arxiv.org/pdf/{arxiv_id}")
    if r.status_code == 200 and r.content[:4] == b"%PDF":
        return "pdf", r.content
    return "none", None
