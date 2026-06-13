import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


def _year(item: dict) -> Optional[int]:
    try:
        return item["issued"]["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        return None


async def search(
    client: httpx.AsyncClient, title: str, mailto: Optional[str] = None, rows: int = 15
) -> List[Candidate]:
    params = {"query.bibliographic": title, "rows": rows}
    if mailto:
        params["mailto"] = mailto
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get("https://api.crossref.org/works", params=params,
                                headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        items = resp.json()["message"]["items"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.debug("Crossref 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for it in items:
        titles = it.get("title") or []
        if not titles:
            continue
        out.append(Candidate(
            title=titles[0],
            doi=it.get("DOI"),
            source="crossref",
            year=_year(it),
        ))
    return out


async def fetch_venue(client: httpx.AsyncClient, doi: str,
                      mailto: Optional[str] = None) -> Optional[str]:
    """从 Crossref JSON 取 venue:期刊用 container-title,预印本用 institution(如 bioRxiv)。"""
    headers = {"User-Agent": USER_AGENT(mailto)}
    params = {"mailto": mailto} if mailto else None
    try:
        resp = await client.get(f"https://api.crossref.org/works/{doi}",
                                params=params, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        msg = resp.json()["message"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.debug("Crossref venue 查询失败: %s", e)
        return None
    ct = msg.get("container-title") or []
    if ct and ct[0]:
        return ct[0]
    inst = msg.get("institution") or []
    if inst and inst[0].get("name"):
        return inst[0]["name"]
    return None
