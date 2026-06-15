import scholar_bibtex.sources.scholar as sch


def test_fetch_returns_none_when_selenium_unavailable(monkeypatch):
    # 模拟 selenium 不可用时优雅降级
    def boom(proxy):
        raise ImportError("no selenium")
    monkeypatch.setattr(sch, "_make_browser", boom)
    out = sch.fetch("some title", proxy=None)
    assert out is None


def test_fetch_uses_browser_when_available(monkeypatch):
    calls = {}

    def fake_make_browser(proxy):
        calls["proxy"] = proxy
        return object()

    def fake_scrape(browser, query):
        calls["query"] = query
        return "@article{scholar2020,\n title={Scraped}\n}"

    monkeypatch.setattr(sch, "_make_browser", fake_make_browser)
    monkeypatch.setattr(sch, "_scrape", fake_scrape)
    monkeypatch.setattr(sch, "_quit_browser", lambda b: None)
    out = sch.fetch("my title", proxy="127.0.0.1:7890")
    assert out.startswith("@article{")
    assert calls["query"] == "my title"
    assert calls["proxy"] == "127.0.0.1:7890"
