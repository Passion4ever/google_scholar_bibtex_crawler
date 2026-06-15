import httpx
import respx

from scholar_bibtex.sources.doi_negotiation import fetch_bibtex


BIB = "@article{x2023,\n title={Foo}\n}"


@respx.mock
async def test_fetch_from_doi_org_success():
    respx.get("https://doi.org/10.1/abc").mock(
        return_value=httpx.Response(200, text=BIB,
                                    headers={"content-type": "application/x-bibtex"})
    )
    async with httpx.AsyncClient() as client:
        out = await fetch_bibtex(client, "10.1/abc", mailto="me@x.com")
    assert out is not None
    assert out.strip().startswith("@article{")


@respx.mock
async def test_falls_back_to_crossref_transform_on_doi_org_failure():
    respx.get("https://doi.org/10.1/abc").mock(return_value=httpx.Response(404))
    respx.get(
        "https://api.crossref.org/works/10.1/abc/transform/application/x-bibtex"
    ).mock(return_value=httpx.Response(200, text=BIB))
    async with httpx.AsyncClient() as client:
        out = await fetch_bibtex(client, "10.1/abc", mailto="me@x.com")
    assert out is not None
    assert "@article{" in out


@respx.mock
async def test_returns_none_when_both_fail():
    respx.get("https://doi.org/10.1/abc").mock(return_value=httpx.Response(404))
    respx.get(
        "https://api.crossref.org/works/10.1/abc/transform/application/x-bibtex"
    ).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        out = await fetch_bibtex(client, "10.1/abc", mailto=None)
    assert out is None
