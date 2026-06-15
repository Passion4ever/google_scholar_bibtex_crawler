import logging
from typing import Optional

import httpx

from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


async def _try(client: httpx.AsyncClient, url: str, headers: dict) -> Optional[str]:
    try:
        resp = await client.get(url, headers=headers, timeout=_TIMEOUT,
                                follow_redirects=True)
    except httpx.HTTPError as e:
        logger.debug("DOI negotiation 请求失败 %s: %s", url, e)
        return None
    if resp.status_code == 200 and "@" in resp.text:
        return resp.text.strip()
    return None


async def fetch_bibtex(
    client: httpx.AsyncClient, doi: str, mailto: Optional[str] = None
) -> Optional[str]:
    """对 DOI 取权威 BibTeX:先 doi.org(HTTPS),失败退 Crossref transform。"""
    headers = {
        "Accept": "application/x-bibtex",
        "User-Agent": USER_AGENT(mailto),
    }
    out = await _try(client, f"https://doi.org/{doi}", headers)
    if out:
        return out
    transform = f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
    return await _try(client, transform, headers)
