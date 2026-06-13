import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


def _strip_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "")


async def search(
    client: httpx.AsyncClient,
    title: str,
    api_key: Optional[str] = None,
    mailto: Optional[str] = None,
    rows: int = 15,
) -> List[Candidate]:
    if not api_key:
        logger.debug("OpenAlex 未配置 API key,跳过")
        return []
    params = {
        "search": title,
        "per-page": rows,
        "api_key": api_key,
    }
    if mailto:
        params["mailto"] = mailto
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get("https://api.openalex.org/works", params=params,
                                headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("OpenAlex 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for it in results:
        title_val = it.get("title")
        if not title_val:
            continue
        out.append(Candidate(
            title=title_val,
            doi=_strip_doi(it.get("doi")),
            source="openalex",
            year=it.get("publication_year"),
        ))
    return out
