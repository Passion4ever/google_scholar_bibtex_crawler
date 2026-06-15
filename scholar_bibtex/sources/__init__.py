import asyncio
import logging

from . import crossref, openalex, dblp, semantic_scholar, scholar
from .doi_negotiation import fetch_bibtex as _doi_fetch
from ..normalize import has_venue, inject_journal
from ..ratelimit import RateLimiter

logger = logging.getLogger(__name__)


class DefaultSources:
    """真实源聚合,带每源限流。供 pipeline.resolve 注入。"""

    def __init__(self):
        self._limiters = {
            "doi": RateLimiter(concurrency=5),
            "crossref": RateLimiter(concurrency=3, min_interval=0.34),
            "openalex": RateLimiter(concurrency=8),
            "dblp": RateLimiter(concurrency=3),
            "semantic_scholar": RateLimiter(concurrency=1, min_interval=1.0),
        }

    async def doi_fetch(self, client, doi, mailto=None):
        async with self._limiters["doi"]:
            bib = await _doi_fetch(client, doi, mailto=mailto)
        # 预印本等缺 journal 的条目:补查 Crossref venue 填进 journal(如 bioRxiv)
        if bib and not has_venue(bib):
            async with self._limiters["crossref"]:
                venue = await crossref.fetch_venue(client, doi, mailto=mailto)
            if venue:
                bib = inject_journal(bib, venue)
        return bib

    async def search_all(self, client, title, cfg):
        tasks = []

        async def run(name, coro_factory):
            async with self._limiters[name]:
                return await coro_factory()

        tasks.append(run("crossref",
                         lambda: crossref.search(client, title, mailto=cfg.mailto)))
        if cfg.use_openalex:
            tasks.append(run("openalex",
                             lambda: openalex.search(client, title,
                                                     api_key=cfg.openalex_key,
                                                     mailto=cfg.mailto)))
        if cfg.use_dblp:
            tasks.append(run("dblp",
                             lambda: dblp.search(client, title, mailto=cfg.mailto)))
        if cfg.use_semantic_scholar:
            tasks.append(run("semantic_scholar",
                             lambda: semantic_scholar.search(
                                 client, title, api_key=cfg.semantic_scholar_key,
                                 mailto=cfg.mailto)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged = []
        for r in results:
            if isinstance(r, Exception):
                logger.debug("某源检索异常: %s", r)
                continue
            merged.extend(r)
        return merged

    async def scholar_fetch(self, query, proxy=None):
        return await asyncio.to_thread(scholar.fetch, query, proxy)
