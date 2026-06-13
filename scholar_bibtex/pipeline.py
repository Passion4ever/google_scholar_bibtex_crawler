import logging

import httpx

from .classify import classify
from .config import Config
from .matching import consolidate
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

    # 标题:并发消歧 + 多源交叉验证
    candidates = await sources.search_all(client, val, cfg)
    decision = consolidate(val, candidates, high=cfg.high, low=cfg.low)

    if decision is not None:
        review = decision.confidence == "review"
        cand = decision.candidate
        # 来源标注:多源印证时附上 agreement,冲突时附上 note
        src = cand.source
        if decision.agreement >= 2:
            src = f"{src}(+{decision.agreement - 1} 源印证)"
        error = decision.note or None
        # 有 DOI → 取权威 BibTeX
        if cand.doi:
            bib = await sources.doi_fetch(client, cand.doi, mailto=cfg.mailto)
            if bib:
                return Result(
                    query=query, bibtex=normalize_bibtex(bib),
                    doi=cand.doi, source=src,
                    confidence=decision.confidence,
                    match_title=cand.title, score=decision.score, review=review,
                    error=error if review else None,
                )
        # 无 DOI 但源有原生 BibTeX
        if cand.bibtex:
            return Result(
                query=query, bibtex=normalize_bibtex(cand.bibtex),
                doi=cand.doi, source=src,
                confidence=decision.confidence,
                match_title=cand.title, score=decision.score, review=review,
                error=error if review else None,
            )

    # 兜底:Google Scholar
    if cfg.use_scholar_fallback:
        bib = await sources.scholar_fetch(query, proxy=cfg.proxy)
        if bib:
            return Result(query=query, bibtex=normalize_bibtex(bib),
                          source="scholar", confidence="review", review=True)

    return Result(query=query, confidence="failed",
                  error="no acceptable match across sources")
