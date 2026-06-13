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


async def test_scholar_fetch_runs_in_executor(monkeypatch):
    import scholar_bibtex.sources as agg

    def fake_fetch(query, proxy=None):
        return "@article{x,}"

    monkeypatch.setattr(agg.scholar, "fetch", fake_fetch)
    src = DefaultSources()
    out = await src.scholar_fetch("q", proxy=None)
    assert out == "@article{x,}"
