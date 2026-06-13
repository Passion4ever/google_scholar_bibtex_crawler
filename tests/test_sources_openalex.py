import httpx
import respx

from scholar_bibtex.sources.openalex import search


RESP = {
    "results": [
        {"title": "Deep learning for genomics",
         "doi": "https://doi.org/10.5/gen",
         "publication_year": 2022},
        {"title": "Unrelated", "doi": None, "publication_year": 2010},
    ]
}


async def test_search_skips_when_no_api_key():
    async with httpx.AsyncClient() as client:
        cands = await search(client, "anything", api_key=None)
    assert cands == []  # 无 key 直接跳过,不发请求


@respx.mock
async def test_search_returns_candidates_with_key():
    respx.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=RESP)
    )
    async with httpx.AsyncClient() as client:
        cands = await search(client, "Deep learning for genomics", api_key="KEY", mailto="m@x.com")
    assert len(cands) == 2
    assert cands[0].doi == "10.5/gen"  # 已剥离 https://doi.org/ 前缀
    assert cands[0].source == "openalex"
    assert cands[0].year == 2022
