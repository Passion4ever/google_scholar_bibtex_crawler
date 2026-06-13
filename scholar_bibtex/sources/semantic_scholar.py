import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)
_FIELDS = "title,externalIds,year,citationStyles"


async def search(
    client: httpx.AsyncClient,
    title: str,
    api_key: Optional[str] = None,
    mailto: Optional[str] = None,
    rows: int = 5,
) -> List[Candidate]:
    params = {"query": title, "limit": rows, "fields": _FIELDS}
    headers = {"User-Agent": USER_AGENT(mailto)}
    if api_key:
        headers["x-api-key"] = api_key
    try:
        resp = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params, headers=headers, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("Semantic Scholar 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for it in data:
        title_val = it.get("title")
        if not title_val:
            continue
        bibtex = (it.get("citationStyles") or {}).get("bibtex")
        doi = (it.get("externalIds") or {}).get("DOI")
        out.append(Candidate(
            title=title_val,
            doi=doi,
            source="semantic_scholar",
            bibtex=bibtex.strip() if bibtex else None,
            year=it.get("year"),
        ))
    return out
