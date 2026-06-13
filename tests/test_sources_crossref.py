import httpx
import respx

from scholar_bibtex.sources.crossref import search, fetch_venue


RESP = {
    "message": {
        "items": [
            {"title": ["Machine learning for protein design"],
             "DOI": "10.1/abc",
             "issued": {"date-parts": [[2024]]}},
            {"title": ["A different paper"], "DOI": "10.2/xyz"},
            {"DOI": "10.3/notitle"},  # 无标题应被跳过
        ]
    }
}


@respx.mock
async def test_search_returns_candidates():
    respx.get("https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json=RESP)
    )
    async with httpx.AsyncClient() as client:
        cands = await search(client, "Machine learning for protein design", mailto="m@x.com")
    assert len(cands) == 2
    assert cands[0].title == "Machine learning for protein design"
    assert cands[0].doi == "10.1/abc"
    assert cands[0].source == "crossref"
    assert cands[0].year == 2024


@respx.mock
async def test_search_empty_on_no_items():
    respx.get("https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json={"message": {"items": []}})
    )
    async with httpx.AsyncClient() as client:
        cands = await search(client, "nothing", mailto=None)
    assert cands == []


@respx.mock
async def test_fetch_venue_prefers_container_title():
    respx.get("https://api.crossref.org/works/10.1/journal").mock(
        return_value=httpx.Response(200, json={"message": {
            "container-title": ["Nature"], "institution": []}}))
    async with httpx.AsyncClient() as client:
        v = await fetch_venue(client, "10.1/journal")
    assert v == "Nature"


@respx.mock
async def test_fetch_venue_falls_back_to_institution_for_preprint():
    respx.get("https://api.crossref.org/works/10.1101/preprint").mock(
        return_value=httpx.Response(200, json={"message": {
            "container-title": [], "institution": [{"name": "bioRxiv"}]}}))
    async with httpx.AsyncClient() as client:
        v = await fetch_venue(client, "10.1101/preprint")
    assert v == "bioRxiv"


@respx.mock
async def test_fetch_venue_none_when_absent():
    respx.get("https://api.crossref.org/works/10.1/x").mock(
        return_value=httpx.Response(200, json={"message": {}}))
    async with httpx.AsyncClient() as client:
        v = await fetch_venue(client, "10.1/x")
    assert v is None
