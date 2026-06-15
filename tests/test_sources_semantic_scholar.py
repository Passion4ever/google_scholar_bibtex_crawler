import httpx
import respx

from scholar_bibtex.sources.semantic_scholar import search


RESP = {
    "data": [
        {"title": "Language models are few-shot learners",
         "externalIds": {"DOI": "10.7/gpt3"},
         "year": 2020,
         "citationStyles": {"bibtex": "@article{brown2020,\n title={...}\n}"}},
        {"title": "No bibtex paper", "year": 2019},
    ]
}


@respx.mock
async def test_search_returns_candidates_with_native_bibtex():
    respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
        return_value=httpx.Response(200, json=RESP)
    )
    async with httpx.AsyncClient() as client:
        cands = await search(client, "Language models are few-shot learners")
    assert len(cands) == 2
    assert cands[0].doi == "10.7/gpt3"
    assert cands[0].source == "semantic_scholar"
    assert cands[0].bibtex.startswith("@article{")
    assert cands[1].bibtex is None


@respx.mock
async def test_search_sends_api_key_header():
    route = respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    async with httpx.AsyncClient() as client:
        await search(client, "q", api_key="SECRET")
    assert route.calls.last.request.headers.get("x-api-key") == "SECRET"
