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
