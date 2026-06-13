import asyncio

from scholar_bibtex.cli import run_batch, parse_args
from scholar_bibtex.config import Config


class StubSources:
    """按 query 返回预设结果,模拟整条管线下游。"""
    def __init__(self, mapping):
        self.mapping = mapping

    async def doi_fetch(self, client, doi, mailto=None):
        return self.mapping.get(doi)

    async def search_all(self, client, title, cfg):
        return []

    async def scholar_fetch(self, query, proxy=None):
        return None


def test_parse_args_defaults():
    args = parse_args(["input.txt"])
    assert args.input == "input.txt"
    assert args.output is None


def test_run_batch_writes_output_and_failed(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("10.1038/ok\n10.2000/missing\n", encoding="utf-8")
    out = tmp_path / "out.bib"

    src = StubSources({"10.1038/ok": "@article{ok,\n title={OK}\n}"})
    cfg = Config.from_env()
    cfg.use_scholar_fallback = False

    asyncio.run(run_batch(str(inp), str(out), cfg=cfg, sources=src))

    text = out.read_text(encoding="utf-8")
    assert "% Query: 10.1038/ok" in text
    assert "@article{ok," in text
    assert "% Query: 10.2000/missing" in text
    assert "% Failed" in text

    failed = (tmp_path / "out.bib.failed.txt").read_text(encoding="utf-8")
    assert "10.2000/missing" in failed


def test_run_batch_skips_comment_and_blank_lines(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("# a comment\n\n10.1038/ok\n  # indented comment\n", encoding="utf-8")
    out = tmp_path / "out.bib"
    src = StubSources({"10.1038/ok": "@article{ok,\n title={OK}\n}"})
    cfg = Config.from_env()
    cfg.use_scholar_fallback = False

    stats = asyncio.run(run_batch(str(inp), str(out), cfg=cfg, sources=src))

    assert stats["success"] == 1
    assert stats["failed"] == []  # 注释行不应被当作查询
    text = out.read_text(encoding="utf-8")
    assert "comment" not in text


def test_run_batch_reports_progress_per_entry(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("10.1038/a\n10.1038/b\n", encoding="utf-8")
    out = tmp_path / "out.bib"
    src = StubSources({"10.1038/a": "@article{a,}", "10.1038/b": "@article{b,}"})
    cfg = Config.from_env(dotenv_path="/nope")
    cfg.use_scholar_fallback = False

    seen = []
    asyncio.run(run_batch(str(inp), str(out), cfg=cfg, sources=src,
                          on_progress=lambda i, total, r: seen.append((i, total, r.query))))

    assert len(seen) == 2                 # 每条都回调一次
    assert {s[0] for s in seen} == {1, 2}  # 计数 1..N
    assert all(s[1] == 2 for s in seen)    # total 正确


def test_run_batch_resumes_skips_done(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("10.1038/ok\n", encoding="utf-8")
    out = tmp_path / "out.bib"
    out.write_text(
        "% Query: 10.1038/ok\n@article{ok,\n title={Cached}\n}\n\n", encoding="utf-8")

    # doi_fetch 若被调用会返回新内容;若断点续传生效则不会被调用
    class FailIfCalled(StubSources):
        async def doi_fetch(self, client, doi, mailto=None):
            raise AssertionError("不应重新抓取已完成条目")

    cfg = Config.from_env()
    cfg.use_scholar_fallback = False
    asyncio.run(run_batch(str(inp), str(out), cfg=cfg, sources=FailIfCalled({})))

    text = out.read_text(encoding="utf-8")
    assert "Cached" in text
