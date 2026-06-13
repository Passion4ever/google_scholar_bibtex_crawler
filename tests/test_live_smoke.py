"""真实联网冒烟测试。默认跳过,设 RUN_LIVE=1 才运行。

    RUN_LIVE=1 CROSSREF_MAILTO=you@example.com python -m pytest tests/test_live_smoke.py -v

验证管线真的能从真实 API 取回权威 BibTeX,并把已知论文匹配到正确 DOI。
不放进默认 CI(会依赖外网、可能 flaky)。
"""
import os

import httpx
import pytest

from scholar_bibtex.config import Config
from scholar_bibtex.pipeline import resolve
from scholar_bibtex.sources import DefaultSources

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1",
    reason="联网测试默认跳过;设 RUN_LIVE=1 启用",
)


def _cfg():
    # 不依赖 key 的源:Crossref + DBLP;关掉 Scholar 兜底
    cfg = Config.from_env()
    cfg.use_scholar_fallback = False
    return cfg


async def test_live_doi_returns_authoritative_bibtex():
    src = DefaultSources()
    async with httpx.AsyncClient() as client:
        r = await resolve("10.1038/s41586-023-06415-8", client=client,
                          sources=src, cfg=_cfg())
    assert r.ok
    assert r.confidence == "exact-doi"
    assert "RFdiffusion" in r.bibtex
    assert r.bibtex.lstrip().startswith("@")


async def test_live_title_resolves_to_correct_doi():
    src = DefaultSources()
    async with httpx.AsyncClient() as client:
        r = await resolve("Design of a novel globular protein fold with atomic-level accuracy",
                          client=client, sources=src, cfg=_cfg())
    assert r.ok
    assert not r.review            # 应高置信
    assert r.doi == "10.1126/science.1089427"   # Top7 (Kuhlman 2003)


async def test_live_auto_accepted_title_matches_query():
    # 安全不变式:被高置信自动采纳(非存疑)的结果,其匹配标题必须与查询几乎一致。
    # 我们绝不"静默采纳一个不同的标题"。
    # (注:同名不同篇的论文如多篇 "Attention Is All You Need" 仍可能被采纳——
    #  这是纯标题输入的固有歧义,但采纳的至少是标题一致的某篇。)
    from scholar_bibtex.matching import score_titles
    src = DefaultSources()
    async with httpx.AsyncClient() as client:
        r = await resolve("Attention is all you need", client=client,
                          sources=src, cfg=_cfg())
    if r.ok and not r.review:
        assert score_titles("Attention is all you need", r.match_title) >= 95
