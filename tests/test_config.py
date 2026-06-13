from scholar_bibtex.config import Config


def test_from_env_reads_keys(monkeypatch):
    monkeypatch.setenv("CROSSREF_MAILTO", "me@x.com")
    monkeypatch.setenv("OPENALEX_API_KEY", "OAKEY")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "S2KEY")
    cfg = Config.from_env()
    assert cfg.mailto == "me@x.com"
    assert cfg.openalex_key == "OAKEY"
    assert cfg.semantic_scholar_key == "S2KEY"


def test_defaults_when_env_absent(monkeypatch):
    for k in ("CROSSREF_MAILTO", "OPENALEX_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    cfg = Config.from_env()
    assert cfg.mailto is None
    assert cfg.openalex_key is None
    assert cfg.high == 95.0
    assert cfg.low == 85.0
    assert cfg.concurrency == 8


def test_overrides_apply():
    cfg = Config.from_env(high=90, low=80, concurrency=4, proxy="1.2.3.4:8080")
    assert cfg.high == 90
    assert cfg.low == 80
    assert cfg.concurrency == 4
    assert cfg.proxy == "1.2.3.4:8080"
