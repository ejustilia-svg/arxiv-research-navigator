"""Общий HTTP-клиент: вежливые паузы (arXiv просит ≤1 запрос / 3 с) и ретраи на 429/5xx."""
from __future__ import annotations

import time

import requests

USER_AGENT = "arxiv-research-navigator/0.1 (student course project)"

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_last_call: dict[str, float] = {}


def get(url: str, *, host_delay: float = 3.0, retries: int = 5, **kw) -> requests.Response:
    return _request("GET", url, host_delay=host_delay, retries=retries, **kw)


def post(url: str, *, host_delay: float = 1.0, retries: int = 5, **kw) -> requests.Response:
    return _request("POST", url, host_delay=host_delay, retries=retries, **kw)


def _request(method: str, url: str, *, host_delay: float, retries: int, **kw) -> requests.Response:
    host = url.split("/")[2]
    kw.setdefault("timeout", 60)
    r: requests.Response | None = None
    for attempt in range(retries):
        wait = _last_call.get(host, 0) + host_delay - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()
        try:
            r = _session.request(method, url, **kw)
        except requests.RequestException:
            time.sleep(2 ** attempt * 3)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            ra = r.headers.get("Retry-After", "")
            time.sleep(int(ra) if ra.isdigit() else 2 ** attempt * 5)
            continue
        return r
    if r is None:  # все попытки упали на сетевой ошибке
        raise requests.ConnectionError(f"{method} {url}: no response after {retries} retries")
    r.raise_for_status()
    return r
