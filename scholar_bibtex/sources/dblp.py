import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


def _int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


async def search(
    client: httpx.AsyncClient, title: str, mailto: Optional[str] = None, rows: int = 15
) -> List[Candidate]:
    params = {"q": title, "format": "json", "h": rows}
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get("https://dblp.org/search/publ/api", params=params,
                                headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        hit = resp.json().get("result", {}).get("hits", {}).get("hit", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("DBLP 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for h in hit:
        info = h.get("info", {})
        title_val = info.get("title")
        if not title_val:
            continue
        out.append(Candidate(
            title=title_val.rstrip("."),
            doi=info.get("doi"),
            source="dblp",
            year=_int(info.get("year")),
        ))
    return out


async def fetch_bib(client: httpx.AsyncClient, rec_url: str,
                    mailto: Optional[str] = None) -> Optional[str]:
    """按 DBLP 记录 URL 取原生 .bib(无 DOI 时的备用)。"""
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get(rec_url.rstrip("/") + ".bib", headers=headers,
                                timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200 and "@" in resp.text:
            return resp.text.strip()
    except httpx.HTTPError as e:
        logger.debug("DBLP .bib 取回失败: %s", e)
    return None
