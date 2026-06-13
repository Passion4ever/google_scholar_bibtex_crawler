import httpx
import pytest

from scholar_bibtex.pipeline import resolve
from scholar_bibtex.config import Config
from scholar_bibtex.models import Candidate


class FakeSources:
    """注入到 pipeline 的可控源集合。"""
    def __init__(self, doi_bibtex=None, candidates=None, scholar_bibtex=None):
        self._doi_bibtex = doi_bibtex
        self._candidates = candidates or []
        self._scholar_bibtex = scholar_bibtex
        self.scholar_called = False

    async def doi_fetch(self, client, doi, mailto=None):
        return self._doi_bibtex

    async def search_all(self, client, title, cfg):
        return list(self._candidates)

    async def scholar_fetch(self, query, proxy=None):
        self.scholar_called = True
        return self._scholar_bibtex


@pytest.fixture
def cfg():
    return Config.from_env()


async def test_doi_input_fetches_authoritative(cfg):
    src = FakeSources(doi_bibtex="@article{a,\n title={Foo}\n}")
    async with httpx.AsyncClient() as client:
        r = await resolve("10.1038/abc", client=client, sources=src, cfg=cfg)
    assert r.ok
    assert r.confidence == "exact-doi"
    assert r.doi == "10.1038/abc"
    assert r.source == "doi.org"


async def test_doi_input_failure_marks_failed(cfg):
    src = FakeSources(doi_bibtex=None)
    async with httpx.AsyncClient() as client:
        r = await resolve("10.1038/abc", client=client, sources=src, cfg=cfg)
    assert not r.ok
    assert r.confidence == "failed"


async def test_title_high_match_fetches_authoritative(cfg):
    cands = [Candidate(title="Exact Title Here", doi="10.2/y", source="crossref")]
    src = FakeSources(candidates=cands, doi_bibtex="@article{y,\n title={Exact Title Here}\n}")
    async with httpx.AsyncClient() as client:
        r = await resolve("Exact Title Here", client=client, sources=src, cfg=cfg)
    assert r.ok
    assert r.confidence == "high"
    assert r.doi == "10.2/y"
    assert r.review is False


async def test_title_mid_match_flags_review(cfg):
    # 分数落在 [low, high) 区间
    cands = [Candidate(title="Exact Title Here extra words appended now",
                       doi="10.2/y", source="crossref")]
    src = FakeSources(candidates=cands, doi_bibtex="@article{y,}")
    async with httpx.AsyncClient() as client:
        r = await resolve("Exact Title Here", client=client, sources=src,
                          cfg=Config.from_env(high=99, low=50))
    assert r.ok
    assert r.review is True
    assert r.confidence == "review"


async def test_title_no_doi_uses_native_bibtex(cfg):
    cands = [Candidate(title="DBLP Only Paper", doi=None, source="dblp",
                       bibtex="@inproceedings{d,\n title={DBLP Only Paper}\n}")]
    src = FakeSources(candidates=cands)
    async with httpx.AsyncClient() as client:
        r = await resolve("DBLP Only Paper", client=client, sources=src, cfg=cfg)
    assert r.ok
    assert r.source == "dblp"
    assert "@inproceedings" in r.bibtex


async def test_title_no_match_falls_back_to_scholar(cfg):
    src = FakeSources(candidates=[], scholar_bibtex="@article{s,\n title={Scholar}\n}")
    async with httpx.AsyncClient() as client:
        r = await resolve("Totally unfindable via apis", client=client, sources=src, cfg=cfg)
    assert src.scholar_called
    assert r.ok
    assert r.source == "scholar"
    assert r.review is True


async def test_title_total_failure_marks_failed(cfg):
    src = FakeSources(candidates=[], scholar_bibtex=None)
    async with httpx.AsyncClient() as client:
        r = await resolve("nothing anywhere", client=client, sources=src, cfg=cfg)
    assert not r.ok
    assert r.confidence == "failed"
