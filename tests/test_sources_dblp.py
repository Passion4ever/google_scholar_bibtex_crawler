import httpx
import respx

from scholar_bibtex.sources.dblp import search


RESP = {
    "result": {
        "hits": {
            "hit": [
                {"info": {"title": "Attention is all you need",
                          "doi": "10.5555/attn",
                          "year": "2017",
                          "url": "https://dblp.org/rec/conf/nips/Vaswani17"}},
                {"info": {"title": "No URL paper", "year": "2020"}},
            ]
        }
    }
}


@respx.mock
async def test_search_returns_candidates_with_bib_url():
    respx.get("https://dblp.org/search/publ/api").mock(
        return_value=httpx.Response(200, json=RESP)
    )
    async with httpx.AsyncClient() as client:
        cands = await search(client, "Attention is all you need")
    assert len(cands) >= 1
    c = cands[0]
    assert c.title == "Attention is all you need"
    assert c.doi == "10.5555/attn"
    assert c.source == "dblp"
    assert c.year == 2017


@respx.mock
async def test_search_empty_on_no_hits():
    respx.get("https://dblp.org/search/publ/api").mock(
        return_value=httpx.Response(200, json={"result": {"hits": {}}})
    )
    async with httpx.AsyncClient() as client:
        cands = await search(client, "nothing")
    assert cands == []
