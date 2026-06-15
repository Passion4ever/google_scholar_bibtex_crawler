import httpx
import respx

from scholar_bibtex.sources import DefaultSources
from scholar_bibtex.config import Config


CROSSREF = {"message": {"items": [
    {"title": ["Paper A"], "DOI": "10.1/a"}]}}
DBLP = {"result": {"hits": {"hit": [
    {"info": {"title": "Paper A", "doi": "10.1/a", "year": "2021"}}]}}}


@respx.mock
async def test_search_all_merges_sources():
    respx.get("https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json=CROSSREF))
    respx.get("https://dblp.org/search/publ/api").mock(
        return_value=httpx.Response(200, json=DBLP))
    # 无 openalex key → 跳过;S2 关闭
    cfg = Config.from_env()
    cfg.use_semantic_scholar = False
    src = DefaultSources()
    async with httpx.AsyncClient() as client:
        cands = await src.search_all(client, "Paper A", cfg)
    sources_seen = {c.source for c in cands}
    assert "crossref" in sources_seen
    assert "dblp" in sources_seen


@respx.mock
async def test_doi_fetch_enriches_missing_venue():
    # 预印本:content negotiation 无 journal → 补查 Crossref venue 注入
    respx.get("https://doi.org/10.1101/preprint").mock(
        return_value=httpx.Response(200, text="@article{x, title={T}, publisher={openRxiv}, month=Aug }"))
    respx.get("https://api.crossref.org/works/10.1101/preprint").mock(
        return_value=httpx.Response(200, json={"message": {
            "container-title": [], "institution": [{"name": "bioRxiv"}]}}))
    src = DefaultSources()
    async with httpx.AsyncClient() as client:
        bib = await src.doi_fetch(client, "10.1101/preprint")
    assert "journal={bioRxiv}" in bib


@respx.mock
async def test_doi_fetch_skips_enrichment_when_venue_present():
    # 已有 journal → 不再补查(只 mock doi.org;若多查 crossref 会因未 mock 报错)
    respx.get("https://doi.org/10.1/has").mock(
        return_value=httpx.Response(200, text="@article{x, title={T}, journal={Nature} }"))
    src = DefaultSources()
    async with httpx.AsyncClient() as client:
        bib = await src.doi_fetch(client, "10.1/has")
    assert "Nature" in bib


async def test_scholar_fetch_runs_in_executor(monkeypatch):
    import scholar_bibtex.sources as agg

    def fake_fetch(query, proxy=None):
        return "@article{x,}"

    monkeypatch.setattr(agg.scholar, "fetch", fake_fetch)
    src = DefaultSources()
    out = await src.scholar_fetch("q", proxy=None)
    assert out == "@article{x,}"
