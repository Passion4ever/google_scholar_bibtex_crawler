import logging

import httpx

from .classify import classify
from .config import Config
from .matching import pick_best
from .models import Result
from .normalize import normalize_bibtex

logger = logging.getLogger(__name__)


async def resolve(query: str, *, client: httpx.AsyncClient, sources, cfg: Config) -> Result:
    """处理一条输入,返回带溯源的 Result。

    sources 需提供:
      - async doi_fetch(client, doi, mailto) -> Optional[str]
      - async search_all(client, title, cfg) -> list[Candidate]
      - async scholar_fetch(query, proxy) -> Optional[str]
    """
    kind, val = classify(query)

    if kind == "doi":
        bib = await sources.doi_fetch(client, val, mailto=cfg.mailto)
        if bib:
            return Result(query=query, bibtex=normalize_bibtex(bib), doi=val,
                          source="doi.org", confidence="exact-doi")
        return Result(query=query, confidence="failed",
                      error="DOI content negotiation failed")

    # 标题:并发消歧
    candidates = await sources.search_all(client, val, cfg)
    best = pick_best(val, candidates, high=cfg.high, low=cfg.low)

    if best is not None:
        review = best.verdict == "review"
        # 有 DOI → 取权威 BibTeX
        if best.candidate.doi:
            bib = await sources.doi_fetch(client, best.candidate.doi, mailto=cfg.mailto)
            if bib:
                return Result(
                    query=query, bibtex=normalize_bibtex(bib),
                    doi=best.candidate.doi, source=best.candidate.source,
                    confidence="review" if review else "high",
                    match_title=best.candidate.title, score=best.score, review=review,
                )
        # 无 DOI 但源有原生 BibTeX
        if best.candidate.bibtex:
            return Result(
                query=query, bibtex=normalize_bibtex(best.candidate.bibtex),
                doi=best.candidate.doi, source=best.candidate.source,
                confidence="review" if review else "high",
                match_title=best.candidate.title, score=best.score, review=review,
            )

    # 兜底:Google Scholar
    if cfg.use_scholar_fallback:
        bib = await sources.scholar_fetch(query, proxy=cfg.proxy)
        if bib:
            return Result(query=query, bibtex=normalize_bibtex(bib),
                          source="scholar", confidence="review", review=True)

    return Result(query=query, confidence="failed",
                  error="no acceptable match across sources")
