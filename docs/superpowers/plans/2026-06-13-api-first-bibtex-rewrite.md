# API 优先批量 BibTeX 工具 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单文件 Scholar 爬虫重写为 API 优先的异步批量工具:DOI 走 content negotiation 取权威 BibTeX,标题先消歧到 DOI 再取权威,严格相似度验证+标记存疑,多源降级,Scholar 仅兜底。

**Architecture:** 小型包 `scholar_bibtex/`。纯函数模块(classify/matching/normalize/progress/models)无网络易测;`sources/` 各源经 `httpx` 异步直连,统一限流重试;`pipeline` 编排每条;`cli` 批量驱动 + 断点续传 + 溯源输出。复用 RapidFuzz / bibtexparser,只写编排层。

**Tech Stack:** Python 3.10+, httpx(async), rapidfuzz, bibtexparser(>=1.4,<2), pytest + pytest-asyncio + respx;Scholar 兜底沿用 undetected-chromedriver/selenium(可选 extra)。

---

## 文件结构

```
scholar_bibtex/
├── __init__.py          # 版本号
├── models.py            # Candidate / Result 数据类
├── classify.py          # DOI vs 标题 识别
├── matching.py          # 标题归一化 + RapidFuzz 相似度 + 阈值判定
├── normalize.py         # bibtexparser 归一化
├── progress.py          # 断点续传解析 + 条目格式化
├── ratelimit.py         # async 限流器 + 重试退避
├── config.py            # 配置(env + 命令行)
├── pipeline.py          # 每条编排:分类→消歧→验证→取权威→归一化
├── cli.py               # argparse + 批量驱动 + 输出
├── __main__.py          # python -m scholar_bibtex 入口
└── sources/
    ├── __init__.py
    ├── base.py          # Candidate 搜索协议 + 共享 http 帮助
    ├── doi_negotiation.py
    ├── crossref.py
    ├── openalex.py
    ├── dblp.py
    ├── semantic_scholar.py
    └── scholar.py       # 复用现有 Selenium,降为兜底
tests/
├── conftest.py
├── test_models.py
├── test_classify.py
├── test_matching.py
├── test_normalize.py
├── test_progress.py
├── test_ratelimit.py
├── test_sources_doi.py
├── test_sources_crossref.py
├── test_sources_openalex.py
├── test_sources_dblp.py
├── test_sources_semantic_scholar.py
├── test_config.py
├── test_pipeline.py
└── test_cli.py
```

---

## Task 0: 脚手架与依赖

**Files:**
- Create: `scholar_bibtex/__init__.py`, `scholar_bibtex/sources/__init__.py`, `tests/conftest.py`, `requirements-dev.txt`, `pytest.ini`
- Modify: `requirements.txt`

- [ ] **Step 1: 创建包目录与版本文件**

`scholar_bibtex/__init__.py`:
```python
__version__ = "0.1.0"
```

`scholar_bibtex/sources/__init__.py`:
```python
```

- [ ] **Step 2: 更新依赖**

`requirements.txt`:
```
httpx>=0.27
rapidfuzz>=3.0
bibtexparser>=1.4,<2
# 可选: Google Scholar 兜底(需本机 Chrome)
undetected-chromedriver>=3.5.0
selenium>=4.0.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.23
respx>=0.21
```

- [ ] **Step 3: pytest 配置**

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 4: 安装并验证**

Run: `pip install -r requirements-dev.txt && python -c "import httpx, rapidfuzz, bibtexparser, respx; print('deps ok')"`
Expected: `deps ok`

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/__init__.py scholar_bibtex/sources/__init__.py requirements.txt requirements-dev.txt pytest.ini tests/conftest.py
git commit -m "chore: scaffold scholar_bibtex package and test deps"
```

---

## Task 1: 数据模型 (models.py)

**Files:**
- Create: `scholar_bibtex/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from scholar_bibtex.models import Candidate, Result


def test_candidate_defaults():
    c = Candidate(title="A Title")
    assert c.title == "A Title"
    assert c.doi is None
    assert c.bibtex is None
    assert c.source == ""


def test_result_ok_true_when_bibtex_present():
    r = Result(query="q", bibtex="@article{x,}")
    assert r.ok is True


def test_result_ok_false_when_no_bibtex():
    r = Result(query="q", error="not found", confidence="failed")
    assert r.ok is False
    assert r.confidence == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scholar_bibtex.models'`

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/models.py`:
```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class Candidate:
    """一个标题查询返回的候选论文。"""
    title: str
    doi: Optional[str] = None
    source: str = ""
    bibtex: Optional[str] = None  # 源若原生提供 BibTeX(如 DBLP/S2)
    year: Optional[int] = None


@dataclass
class Result:
    """一条输入的最终处理结果。"""
    query: str
    bibtex: Optional[str] = None
    doi: Optional[str] = None
    source: str = ""
    confidence: str = ""        # exact-doi | high | review | failed
    match_title: Optional[str] = None
    score: Optional[float] = None
    review: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.bibtex is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/models.py tests/test_models.py
git commit -m "feat: add Candidate and Result data models"
```

---

## Task 2: 输入分类 (classify.py)

**Files:**
- Create: `scholar_bibtex/classify.py`
- Test: `tests/test_classify.py`

- [ ] **Step 1: Write the failing test**

`tests/test_classify.py`:
```python
from scholar_bibtex.classify import classify


def test_raw_doi():
    assert classify("10.1038/s41586-023-06415-8") == ("doi", "10.1038/s41586-023-06415-8")


def test_doi_with_url_prefix():
    assert classify("https://doi.org/10.1038/abc123") == ("doi", "10.1038/abc123")


def test_doi_with_scheme_prefix():
    assert classify("doi:10.1145/3292500.3330701") == ("doi", "10.1145/3292500.3330701")


def test_plain_title():
    kind, val = classify("Machine learning for functional protein design")
    assert kind == "title"
    assert val == "Machine learning for functional protein design"


def test_title_with_periods_is_not_doi():
    kind, _ = classify("E. coli growth under stress. A review.")
    assert kind == "title"


def test_strips_whitespace():
    assert classify("  10.1000/xyz  ") == ("doi", "10.1000/xyz")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classify.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/classify.py`:
```python
import re
from typing import Tuple

_DOI_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$",
    re.IGNORECASE,
)


def classify(query: str) -> Tuple[str, str]:
    """判定输入是 DOI 还是标题。

    返回 ("doi", 规范化DOI) 或 ("title", 去空白标题)。
    """
    q = query.strip()
    m = _DOI_RE.match(q)
    if m:
        return ("doi", m.group(1))
    return ("title", q)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classify.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/classify.py tests/test_classify.py
git commit -m "feat: add DOI vs title classifier"
```

---

## Task 3: 标题匹配与验证 (matching.py)

**Files:**
- Create: `scholar_bibtex/matching.py`
- Test: `tests/test_matching.py`

- [ ] **Step 1: Write the failing test**

`tests/test_matching.py`:
```python
from scholar_bibtex.matching import normalize_title, score_titles, verdict, pick_best
from scholar_bibtex.models import Candidate


def test_normalize_lowercases_and_strips_punct():
    assert normalize_title("Hello, World! A Study.") == "hello world a study"


def test_exact_match_scores_100():
    assert score_titles("Deep Learning", "Deep Learning") == 100


def test_word_order_insensitive():
    s = score_titles("protein design machine learning",
                     "machine learning protein design")
    assert s >= 95


def test_wrong_paper_scores_low():
    s = score_titles("Attention is all you need",
                     "A survey of reinforcement learning")
    assert s < 85


def test_verdict_thresholds():
    assert verdict(99) == "high"
    assert verdict(90) == "review"
    assert verdict(50) == "reject"
    assert verdict(95) == "high"
    assert verdict(85) == "review"


def test_pick_best_prefers_highest_score_with_doi():
    cands = [
        Candidate(title="Totally different paper", doi="10.1/x", source="openalex"),
        Candidate(title="Machine learning for protein design", doi="10.2/y", source="crossref"),
    ]
    best = pick_best("Machine learning for protein design", cands)
    assert best is not None
    assert best.candidate.doi == "10.2/y"
    assert best.verdict == "high"


def test_pick_best_tiebreak_prefers_source_priority():
    cands = [
        Candidate(title="Same Title", doi="10.1/a", source="semantic_scholar"),
        Candidate(title="Same Title", doi="10.2/b", source="crossref"),
    ]
    best = pick_best("Same Title", cands,
                     source_priority=["crossref", "openalex", "dblp", "semantic_scholar"])
    assert best.candidate.source == "crossref"


def test_pick_best_returns_none_when_all_below_low():
    cands = [Candidate(title="Unrelated work about cats", source="crossref")]
    best = pick_best("Quantum gravity and black holes", cands)
    assert best is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_matching.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/matching.py`:
```python
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from rapidfuzz import fuzz

from .models import Candidate

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

HIGH_DEFAULT = 95.0
LOW_DEFAULT = 85.0
DEFAULT_SOURCE_PRIORITY = ["crossref", "openalex", "dblp", "semantic_scholar"]


def normalize_title(title: str) -> str:
    t = title.lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def score_titles(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(normalize_title(a), normalize_title(b))


def verdict(score: float, high: float = HIGH_DEFAULT, low: float = LOW_DEFAULT) -> str:
    if score >= high:
        return "high"
    if score >= low:
        return "review"
    return "reject"


@dataclass
class Match:
    candidate: Candidate
    score: float
    verdict: str


def pick_best(
    query_title: str,
    candidates: Sequence[Candidate],
    high: float = HIGH_DEFAULT,
    low: float = LOW_DEFAULT,
    source_priority: Optional[List[str]] = None,
) -> Optional[Match]:
    """从候选中选最佳;无任何 >= low 的返回 None。

    排序键:分数降序 → 有DOI优先 → 源优先级。
    """
    priority = source_priority or DEFAULT_SOURCE_PRIORITY

    def rank(c: Candidate):
        s = score_titles(query_title, c.title)
        has_doi = 1 if c.doi else 0
        try:
            src_rank = priority.index(c.source)
        except ValueError:
            src_rank = len(priority)
        return (-s, -has_doi, src_rank)

    scored = sorted(candidates, key=rank)
    if not scored:
        return None
    best = scored[0]
    s = score_titles(query_title, best.title)
    v = verdict(s, high, low)
    if v == "reject":
        return None
    return Match(candidate=best, score=s, verdict=v)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_matching.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/matching.py tests/test_matching.py
git commit -m "feat: add title matching, verdict thresholds, and pick_best"
```

---

## Task 4: BibTeX 归一化 (normalize.py)

**Files:**
- Create: `scholar_bibtex/normalize.py`
- Test: `tests/test_normalize.py`

- [ ] **Step 1: Write the failing test**

`tests/test_normalize.py`:
```python
from scholar_bibtex.normalize import normalize_bibtex


RAW = """@article{Key2023,
title={A Study},
author={Doe, Jane and Smith, John},
journal={Nature}, year={2023}, volume={1}}"""


def test_normalize_returns_parseable_bibtex():
    out = normalize_bibtex(RAW)
    assert out.strip().startswith("@article{")
    assert "title" in out
    assert "author" in out


def test_normalize_is_idempotent():
    once = normalize_bibtex(RAW)
    twice = normalize_bibtex(once)
    assert once == twice


def test_normalize_consistent_field_order():
    out = normalize_bibtex(RAW)
    # title 出现在 author 之前(固定显示顺序)
    assert out.index("title") < out.index("author")


def test_normalize_bad_input_returns_original():
    junk = "this is not bibtex at all"
    assert normalize_bibtex(junk) == junk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/normalize.py`:
```python
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bparser import BibTexParser

_DISPLAY_ORDER = (
    "title", "author", "journal", "booktitle", "year",
    "volume", "number", "pages", "publisher", "doi", "url",
)


def normalize_bibtex(raw: str) -> str:
    """解析后用固定字段顺序/缩进重新输出;解析失败原样返回。"""
    try:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.loads(raw, parser=parser)
        if not db.entries:
            return raw
        writer = BibTexWriter()
        writer.indent = "  "
        writer.order_entries_by = None  # 保持输入顺序
        writer.display_order = _DISPLAY_ORDER
        return bibtexparser.dumps(db, writer=writer).strip()
    except Exception:
        return raw
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/normalize.py tests/test_normalize.py
git commit -m "feat: add bibtexparser-based BibTeX normalization"
```

---

## Task 5: 断点续传与输出 (progress.py)

**Files:**
- Create: `scholar_bibtex/progress.py`
- Test: `tests/test_progress.py`

- [ ] **Step 1: Write the failing test**

`tests/test_progress.py`:
```python
from scholar_bibtex.progress import load_done, format_entry
from scholar_bibtex.models import Result


SAMPLE = """% Query: 10.1038/abc
% Source: doi.org(crossref) | Confidence: exact-doi
@article{x2023,
  title={Foo}
}

% Query: failed paper
% Failed
% Reason: no candidates

% Query: another good one
@inproceedings{y2024,
  title={Bar}
}
"""


def test_load_done_only_keeps_success(tmp_path):
    p = tmp_path / "out.bib"
    p.write_text(SAMPLE, encoding="utf-8")
    done = load_done(str(p))
    assert "10.1038/abc" in done
    assert "another good one" in done
    assert "failed paper" not in done  # 失败条目可重试


def test_load_done_missing_file(tmp_path):
    assert load_done(str(tmp_path / "nope.bib")) == {}


def test_format_entry_success_has_provenance():
    r = Result(query="some title", bibtex="@article{z,}", doi="10.9/z",
               source="crossref", confidence="high", match_title="some title", score=99.0)
    out = format_entry(r)
    assert out.startswith("% Query: some title\n")
    assert "% Source: crossref" in out
    assert "@article{z,}" in out
    assert out.endswith("\n\n")


def test_format_entry_review_has_review_marker():
    r = Result(query="ambiguous", bibtex="@article{z,}", source="openalex",
               confidence="review", match_title="close title", score=88.0, review=True)
    out = format_entry(r)
    assert "% REVIEW:" in out
    assert "close title" in out
    assert "88" in out


def test_format_entry_failed_writes_reason():
    r = Result(query="missing", confidence="failed", error="no candidates")
    out = format_entry(r)
    assert "% Query: missing" in out
    assert "% Failed" in out
    assert "no candidates" in out
    assert "@" not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_progress.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/progress.py`:
```python
import logging
import os
from typing import Dict

from .models import Result

logger = logging.getLogger(__name__)


def load_done(output_file: str) -> Dict[str, str]:
    """解析已有输出,返回 {query: bibtex},仅含取到 @ 内容的成功条目。

    失败/无内容条目不计入,以便断点续传时重试。
    """
    done: Dict[str, str] = {}
    if not os.path.exists(output_file):
        return done
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError, UnicodeDecodeError) as e:
        logger.warning("读取进度文件失败: %s", e)
        return done

    current = None
    buffer = []

    def flush():
        if current is not None:
            block = "\n".join(buffer).strip()
            # 去掉块内以 % 开头的注释行后,看是否有 @ 实体
            body = "\n".join(
                ln for ln in block.splitlines() if not ln.lstrip().startswith("%")
            ).strip()
            if body.startswith("@"):
                done[current] = body

    for line in content.splitlines():
        if line.startswith("% Query:"):
            flush()
            current = line.replace("% Query:", "").strip()
            buffer = []
        else:
            buffer.append(line)
    flush()
    return done


def format_entry(result: Result) -> str:
    """把一条 Result 渲染为带溯源注释的 .bib 文本块(末尾含空行)。"""
    lines = [f"% Query: {result.query}"]
    if result.ok:
        if result.review:
            lines.append(
                f'% REVIEW: 匹配到 "{result.match_title}" '
                f"score={result.score:.0f} via {result.source} —— 请人工核对"
            )
        else:
            conf = result.confidence
            detail = f"% Source: {result.source} | Confidence: {conf}"
            if result.match_title and result.score is not None:
                detail += f' | Match: "{result.match_title}" score={result.score:.0f}'
            lines.append(detail)
        lines.append(result.bibtex)
    else:
        lines.append("% Failed")
        if result.error:
            lines.append(f"% Reason: {result.error}")
    return "\n".join(lines) + "\n\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_progress.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/progress.py tests/test_progress.py
git commit -m "feat: add resume parsing and provenance-annotated entry formatting"
```

---

## Task 6: 异步限流器 (ratelimit.py)

**Files:**
- Create: `scholar_bibtex/ratelimit.py`
- Test: `tests/test_ratelimit.py`

- [ ] **Step 1: Write the failing test**

`tests/test_ratelimit.py`:
```python
import asyncio
import time

import pytest

from scholar_bibtex.ratelimit import RateLimiter, with_retry, TransientError


async def test_concurrency_cap_enforced():
    limiter = RateLimiter(concurrency=2)
    active = 0
    peak = 0

    async def worker():
        nonlocal active, peak
        async with limiter:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1

    await asyncio.gather(*[worker() for _ in range(6)])
    assert peak <= 2


async def test_min_interval_spaces_requests():
    limiter = RateLimiter(concurrency=5, min_interval=0.05)
    start = time.monotonic()

    async def worker():
        async with limiter:
            pass

    await asyncio.gather(*[worker() for _ in range(3)])
    elapsed = time.monotonic() - start
    # 3 次至少间隔 2 个 min_interval
    assert elapsed >= 0.09


async def test_with_retry_succeeds_after_transient():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("boom")
        return "ok"

    result = await with_retry(flaky, retries=3, base=0.001)
    assert result == "ok"
    assert calls["n"] == 3


async def test_with_retry_reraises_after_exhaustion():
    async def always_fail():
        raise TransientError("nope")

    with pytest.raises(TransientError):
        await with_retry(always_fail, retries=2, base=0.001)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/ratelimit.py`:
```python
import asyncio
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class TransientError(Exception):
    """可重试的临时错误(超时、429、5xx 等)。"""


class RateLimiter:
    """信号量限并发 + 可选最小请求间隔。"""

    def __init__(self, concurrency: int = 3, min_interval: float = 0.0):
        self._sem = asyncio.Semaphore(concurrency)
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self):
        await self._sem.acquire()
        if self._min_interval > 0:
            async with self._lock:
                now = time.monotonic()
                wait = self._last + self._min_interval - now
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = time.monotonic()
        return self

    async def __aexit__(self, *exc):
        self._sem.release()
        return False


async def with_retry(
    factory: Callable[[], Awaitable[T]],
    retries: int = 3,
    base: float = 0.5,
) -> T:
    """对返回 awaitable 的工厂做指数退避重试,仅捕获 TransientError。"""
    last = None
    for attempt in range(retries):
        try:
            return await factory()
        except TransientError as e:
            last = e
            if attempt == retries - 1:
                raise
            await asyncio.sleep(base * (2 ** attempt))
    assert last is not None
    raise last
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/ratelimit.py tests/test_ratelimit.py
git commit -m "feat: add async RateLimiter and with_retry backoff"
```

---

## Task 7: 源基础设施 (sources/base.py)

**Files:**
- Create: `scholar_bibtex/sources/base.py`
- Test: `tests/test_sources_doi.py`(本任务仅放一个占位 import 测试,后续任务补充)

- [ ] **Step 1: Write the failing test**

`tests/test_sources_base.py`:
```python
from scholar_bibtex.sources.base import USER_AGENT, classify_http_error
from scholar_bibtex.ratelimit import TransientError
import pytest


def test_user_agent_includes_mailto_when_given():
    ua = USER_AGENT(mailto="me@example.com")
    assert "me@example.com" in ua


def test_user_agent_without_mailto():
    ua = USER_AGENT(mailto=None)
    assert "scholar_bibtex" in ua


def test_classify_http_error_429_is_transient():
    with pytest.raises(TransientError):
        classify_http_error(429)


def test_classify_http_error_503_is_transient():
    with pytest.raises(TransientError):
        classify_http_error(503)


def test_classify_http_error_404_not_transient():
    # 404 等客户端错误不抛 TransientError(返回 None 让调用方处理)
    assert classify_http_error(404) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_base.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/base.py`:
```python
from typing import Optional

from .. import __version__
from ..ratelimit import TransientError


def USER_AGENT(mailto: Optional[str]) -> str:
    base = f"scholar_bibtex/{__version__}"
    if mailto:
        return f"{base} (mailto:{mailto})"
    return base


def classify_http_error(status: int) -> None:
    """429 / 5xx 抛 TransientError(可重试);其余返回 None。"""
    if status == 429 or 500 <= status < 600:
        raise TransientError(f"HTTP {status}")
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_base.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/base.py tests/test_sources_base.py
git commit -m "feat: add source base helpers (user-agent, http error classification)"
```

---

## Task 8: DOI content negotiation (sources/doi_negotiation.py)

**Files:**
- Create: `scholar_bibtex/sources/doi_negotiation.py`
- Test: `tests/test_sources_doi.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_doi.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_doi.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/doi_negotiation.py`:
```python
import logging
from typing import Optional

import httpx

from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


async def _try(client: httpx.AsyncClient, url: str, headers: dict) -> Optional[str]:
    try:
        resp = await client.get(url, headers=headers, timeout=_TIMEOUT,
                                follow_redirects=True)
    except httpx.HTTPError as e:
        logger.debug("DOI negotiation 请求失败 %s: %s", url, e)
        return None
    if resp.status_code == 200 and "@" in resp.text:
        return resp.text.strip()
    return None


async def fetch_bibtex(
    client: httpx.AsyncClient, doi: str, mailto: Optional[str] = None
) -> Optional[str]:
    """对 DOI 取权威 BibTeX:先 doi.org(HTTPS),失败退 Crossref transform。"""
    headers = {
        "Accept": "application/x-bibtex",
        "User-Agent": USER_AGENT(mailto),
    }
    out = await _try(client, f"https://doi.org/{doi}", headers)
    if out:
        return out
    transform = f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
    return await _try(client, transform, headers)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_doi.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/doi_negotiation.py tests/test_sources_doi.py
git commit -m "feat: add DOI content negotiation with crossref transform fallback"
```

---

## Task 9: Crossref 标题检索 (sources/crossref.py)

**Files:**
- Create: `scholar_bibtex/sources/crossref.py`
- Test: `tests/test_sources_crossref.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_crossref.py`:
```python
import httpx
import respx

from scholar_bibtex.sources.crossref import search


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_crossref.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/crossref.py`:
```python
import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


def _year(item: dict) -> Optional[int]:
    try:
        return item["issued"]["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        return None


async def search(
    client: httpx.AsyncClient, title: str, mailto: Optional[str] = None, rows: int = 5
) -> List[Candidate]:
    params = {"query.bibliographic": title, "rows": rows}
    if mailto:
        params["mailto"] = mailto
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get("https://api.crossref.org/works", params=params,
                                headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        items = resp.json()["message"]["items"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.debug("Crossref 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for it in items:
        titles = it.get("title") or []
        if not titles:
            continue
        out.append(Candidate(
            title=titles[0],
            doi=it.get("DOI"),
            source="crossref",
            year=_year(it),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_crossref.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/crossref.py tests/test_sources_crossref.py
git commit -m "feat: add Crossref bibliographic title search source"
```

---

## Task 10: OpenAlex 标题检索 (sources/openalex.py)

**Files:**
- Create: `scholar_bibtex/sources/openalex.py`
- Test: `tests/test_sources_openalex.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_openalex.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_openalex.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/openalex.py`:
```python
import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


def _strip_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "")


async def search(
    client: httpx.AsyncClient,
    title: str,
    api_key: Optional[str] = None,
    mailto: Optional[str] = None,
    rows: int = 5,
) -> List[Candidate]:
    if not api_key:
        logger.debug("OpenAlex 未配置 API key,跳过")
        return []
    params = {
        "search": title,
        "per-page": rows,
        "api_key": api_key,
    }
    if mailto:
        params["mailto"] = mailto
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get("https://api.openalex.org/works", params=params,
                                headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("OpenAlex 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for it in results:
        title_val = it.get("title")
        if not title_val:
            continue
        out.append(Candidate(
            title=title_val,
            doi=_strip_doi(it.get("doi")),
            source="openalex",
            year=it.get("publication_year"),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_openalex.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/openalex.py tests/test_sources_openalex.py
git commit -m "feat: add OpenAlex title search source (skips without API key)"
```

---

## Task 11: DBLP 标题检索 + 原生 .bib (sources/dblp.py)

**Files:**
- Create: `scholar_bibtex/sources/dblp.py`
- Test: `tests/test_sources_dblp.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_dblp.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_dblp.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/dblp.py`:
```python
import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)


def _int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


async def search(
    client: httpx.AsyncClient, title: str, mailto: Optional[str] = None, rows: int = 5
) -> List[Candidate]:
    params = {"q": title, "format": "json", "h": rows}
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get("https://dblp.org/search/publ/api", params=params,
                                headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        hit = resp.json().get("result", {}).get("hits", {}).get("hit", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("DBLP 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for h in hit:
        info = h.get("info", {})
        title_val = info.get("title")
        if not title_val:
            continue
        out.append(Candidate(
            title=title_val.rstrip("."),
            doi=info.get("doi"),
            source="dblp",
            year=_int(info.get("year")),
        ))
    return out


async def fetch_bib(client: httpx.AsyncClient, rec_url: str,
                    mailto: Optional[str] = None) -> Optional[str]:
    """按 DBLP 记录 URL 取原生 .bib(无 DOI 时的备用)。"""
    headers = {"User-Agent": USER_AGENT(mailto)}
    try:
        resp = await client.get(rec_url.rstrip("/") + ".bib", headers=headers,
                                timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200 and "@" in resp.text:
            return resp.text.strip()
    except httpx.HTTPError as e:
        logger.debug("DBLP .bib 取回失败: %s", e)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_dblp.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/dblp.py tests/test_sources_dblp.py
git commit -m "feat: add DBLP title search source with native .bib fetch"
```

---

## Task 12: Semantic Scholar 标题检索 (sources/semantic_scholar.py)

**Files:**
- Create: `scholar_bibtex/sources/semantic_scholar.py`
- Test: `tests/test_sources_semantic_scholar.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_semantic_scholar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_semantic_scholar.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/semantic_scholar.py`:
```python
import logging
from typing import List, Optional

import httpx

from ..models import Candidate
from .base import USER_AGENT

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0)
_FIELDS = "title,externalIds,year,citationStyles"


async def search(
    client: httpx.AsyncClient,
    title: str,
    api_key: Optional[str] = None,
    mailto: Optional[str] = None,
    rows: int = 5,
) -> List[Candidate]:
    params = {"query": title, "limit": rows, "fields": _FIELDS}
    headers = {"User-Agent": USER_AGENT(mailto)}
    if api_key:
        headers["x-api-key"] = api_key
    try:
        resp = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params, headers=headers, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("Semantic Scholar 检索失败: %s", e)
        return []

    out: List[Candidate] = []
    for it in data:
        title_val = it.get("title")
        if not title_val:
            continue
        bibtex = (it.get("citationStyles") or {}).get("bibtex")
        doi = (it.get("externalIds") or {}).get("DOI")
        out.append(Candidate(
            title=title_val,
            doi=doi,
            source="semantic_scholar",
            bibtex=bibtex.strip() if bibtex else None,
            year=it.get("year"),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_semantic_scholar.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/semantic_scholar.py tests/test_sources_semantic_scholar.py
git commit -m "feat: add Semantic Scholar source with native bibtex"
```

---

## Task 13: Scholar 兜底封装 (sources/scholar.py)

复用现有 `get_google_scholar_bibtex.py` 的抓取逻辑,封装成一个同步函数,供 pipeline 在线程池调用。**懒导入** selenium,使测试无需安装。

**Files:**
- Create: `scholar_bibtex/sources/scholar.py`
- Test: `tests/test_sources_scholar.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_scholar.py`:
```python
import scholar_bibtex.sources.scholar as sch


def test_fetch_returns_none_when_selenium_unavailable(monkeypatch):
    # 模拟 selenium 不可用时优雅降级
    def boom():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_scholar.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/scholar.py`:
```python
"""Google Scholar 兜底抓取。仅在 API 全未命中时调用。

懒导入 selenium/undetected-chromedriver,使核心无需这些依赖。
实际抓取逻辑复用项目根目录的 get_google_scholar_bibtex.py。
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _make_browser(proxy: Optional[str]):
    import get_google_scholar_bibtex as legacy  # 懒导入
    return legacy.create_browser(proxy=proxy)


def _scrape(browser, query: str) -> Optional[str]:
    import get_google_scholar_bibtex as legacy
    from selenium.webdriver.support.ui import WebDriverWait
    wait = WebDriverWait(browser, 15)
    if legacy.check_captcha(browser):
        legacy.wait_for_captcha(browser)
    return legacy.get_bibtex(browser, wait, query)


def _quit_browser(browser) -> None:
    try:
        browser.quit()
    except Exception as e:
        logger.debug("关闭浏览器失败: %s", e)


def fetch(query: str, proxy: Optional[str] = None) -> Optional[str]:
    """同步:启动浏览器抓一条;任何异常都降级为 None。"""
    browser = None
    try:
        browser = _make_browser(proxy)
        return _scrape(browser, query)
    except Exception as e:
        logger.warning("Scholar 兜底失败: %s", e)
        return None
    finally:
        if browser is not None:
            _quit_browser(browser)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_scholar.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/scholar.py tests/test_sources_scholar.py
git commit -m "feat: add Google Scholar backstop wrapper (lazy selenium import)"
```

---

## Task 14: 配置 (config.py)

**Files:**
- Create: `scholar_bibtex/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/config.py`:
```python
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    mailto: Optional[str] = None
    openalex_key: Optional[str] = None
    semantic_scholar_key: Optional[str] = None
    proxy: Optional[str] = None
    high: float = 95.0
    low: float = 85.0
    concurrency: int = 8
    use_openalex: bool = True
    use_semantic_scholar: bool = True
    use_dblp: bool = True
    use_scholar_fallback: bool = True

    @classmethod
    def from_env(cls, **overrides) -> "Config":
        base = dict(
            mailto=os.environ.get("CROSSREF_MAILTO") or None,
            openalex_key=os.environ.get("OPENALEX_API_KEY") or None,
            semantic_scholar_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None,
        )
        base.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**base)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/config.py tests/test_config.py
git commit -m "feat: add Config from env with overrides"
```

---

## Task 15: 编排管线 (pipeline.py)

核心逻辑。用依赖注入(传入 source 搜索函数与 fetch 函数),使测试无网络。

**Files:**
- Create: `scholar_bibtex/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
import httpx
import pytest

from scholar_bibtex.pipeline import resolve
from scholar_bibtex.config import Config
from scholar_bibtex.models import Candidate


class FakeSources:
    """注入到 pipeline 的可控源集合。"""
    def __init__(self, doi_bibtex=None, candidates=None, scholar_bibtex=None):
        self._doi_bibtex = doi_bibtex
        self._candidates = candidates or []
        self._scholar_bibtex = scholar_bibtex
        self.scholar_called = False

    async def doi_fetch(self, client, doi, mailto=None):
        return self._doi_bibtex

    async def search_all(self, client, title, cfg):
        return list(self._candidates)

    async def scholar_fetch(self, query, proxy=None):
        self.scholar_called = True
        return self._scholar_bibtex


@pytest.fixture
def cfg():
    return Config.from_env()


async def test_doi_input_fetches_authoritative(cfg):
    src = FakeSources(doi_bibtex="@article{a,\n title={Foo}\n}")
    async with httpx.AsyncClient() as client:
        r = await resolve("10.1/abc", client=client, sources=src, cfg=cfg)
    assert r.ok
    assert r.confidence == "exact-doi"
    assert r.doi == "10.1/abc"
    assert r.source == "doi.org"


async def test_doi_input_failure_marks_failed(cfg):
    src = FakeSources(doi_bibtex=None)
    async with httpx.AsyncClient() as client:
        r = await resolve("10.1/abc", client=client, sources=src, cfg=cfg)
    assert not r.ok
    assert r.confidence == "failed"


async def test_title_high_match_fetches_authoritative(cfg):
    cands = [Candidate(title="Exact Title Here", doi="10.2/y", source="crossref")]
    src = FakeSources(candidates=cands, doi_bibtex="@article{y,\n title={Exact Title Here}\n}")
    async with httpx.AsyncClient() as client:
        r = await resolve("Exact Title Here", client=client, sources=src, cfg=cfg)
    assert r.ok
    assert r.confidence == "high"
    assert r.doi == "10.2/y"
    assert r.review is False


async def test_title_mid_match_flags_review(cfg):
    # 分数落在 [low, high) 区间
    cands = [Candidate(title="Exact Title Here extra words appended now",
                       doi="10.2/y", source="crossref")]
    src = FakeSources(candidates=cands, doi_bibtex="@article{y,}")
    async with httpx.AsyncClient() as client:
        r = await resolve("Exact Title Here", client=client, sources=src,
                          cfg=Config.from_env(high=99, low=50))
    assert r.ok
    assert r.review is True
    assert r.confidence == "review"


async def test_title_no_doi_uses_native_bibtex(cfg):
    cands = [Candidate(title="DBLP Only Paper", doi=None, source="dblp",
                       bibtex="@inproceedings{d,\n title={DBLP Only Paper}\n}")]
    src = FakeSources(candidates=cands)
    async with httpx.AsyncClient() as client:
        r = await resolve("DBLP Only Paper", client=client, sources=src, cfg=cfg)
    assert r.ok
    assert r.source == "dblp"
    assert "@inproceedings" in r.bibtex


async def test_title_no_match_falls_back_to_scholar(cfg):
    src = FakeSources(candidates=[], scholar_bibtex="@article{s,\n title={Scholar}\n}")
    async with httpx.AsyncClient() as client:
        r = await resolve("Totally unfindable via apis", client=client, sources=src, cfg=cfg)
    assert src.scholar_called
    assert r.ok
    assert r.source == "scholar"
    assert r.review is True


async def test_title_total_failure_marks_failed(cfg):
    src = FakeSources(candidates=[], scholar_bibtex=None)
    async with httpx.AsyncClient() as client:
        r = await resolve("nothing anywhere", client=client, sources=src, cfg=cfg)
    assert not r.ok
    assert r.confidence == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/pipeline.py`:
```python
import logging

import httpx

from .classify import classify
from .config import Config
from .matching import pick_best
from .models import Result
from .normalize import normalize_bibtex

logger = logging.getLogger(__name__)


async def resolve(query: str, *, client: httpx.AsyncClient, sources, cfg: Config) -> Result:
    """处理一条输入,返回带溯源的 Result。

    sources 需提供:
      - async doi_fetch(client, doi, mailto) -> Optional[str]
      - async search_all(client, title, cfg) -> list[Candidate]
      - async scholar_fetch(query, proxy) -> Optional[str]
    """
    kind, val = classify(query)

    if kind == "doi":
        bib = await sources.doi_fetch(client, val, mailto=cfg.mailto)
        if bib:
            return Result(query=query, bibtex=normalize_bibtex(bib), doi=val,
                          source="doi.org", confidence="exact-doi")
        return Result(query=query, confidence="failed",
                      error="DOI content negotiation failed")

    # 标题:并发消歧
    candidates = await sources.search_all(client, val, cfg)
    best = pick_best(val, candidates, high=cfg.high, low=cfg.low)

    if best is not None:
        review = best.verdict == "review"
        # 有 DOI → 取权威 BibTeX
        if best.candidate.doi:
            bib = await sources.doi_fetch(client, best.candidate.doi, mailto=cfg.mailto)
            if bib:
                return Result(
                    query=query, bibtex=normalize_bibtex(bib),
                    doi=best.candidate.doi, source=best.candidate.source,
                    confidence="review" if review else "high",
                    match_title=best.candidate.title, score=best.score, review=review,
                )
        # 无 DOI 但源有原生 BibTeX
        if best.candidate.bibtex:
            return Result(
                query=query, bibtex=normalize_bibtex(best.candidate.bibtex),
                doi=best.candidate.doi, source=best.candidate.source,
                confidence="review" if review else "high",
                match_title=best.candidate.title, score=best.score, review=review,
            )

    # 兜底:Google Scholar
    if cfg.use_scholar_fallback:
        bib = await sources.scholar_fetch(query, proxy=cfg.proxy)
        if bib:
            return Result(query=query, bibtex=normalize_bibtex(bib),
                          source="scholar", confidence="review", review=True)

    return Result(query=query, confidence="failed",
                  error="no acceptable match across sources")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/pipeline.py tests/test_pipeline.py
git commit -m "feat: add per-entry resolve pipeline with source ladder"
```

---

## Task 16: 真实源聚合器 (sources/__init__.py 的 DefaultSources)

把各源 search 函数聚合为 pipeline 期望的 `sources` 对象,带每源限流。

**Files:**
- Modify: `scholar_bibtex/sources/__init__.py`
- Test: `tests/test_sources_aggregate.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources_aggregate.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources_aggregate.py -v`
Expected: FAIL — `ImportError: cannot import name 'DefaultSources'`

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/sources/__init__.py`:
```python
import asyncio
import logging

from . import crossref, openalex, dblp, semantic_scholar, scholar
from .doi_negotiation import fetch_bibtex as _doi_fetch
from ..ratelimit import RateLimiter

logger = logging.getLogger(__name__)


class DefaultSources:
    """真实源聚合,带每源限流。供 pipeline.resolve 注入。"""

    def __init__(self):
        self._limiters = {
            "doi": RateLimiter(concurrency=5),
            "crossref": RateLimiter(concurrency=3, min_interval=0.34),
            "openalex": RateLimiter(concurrency=8),
            "dblp": RateLimiter(concurrency=3),
            "semantic_scholar": RateLimiter(concurrency=1, min_interval=1.0),
        }

    async def doi_fetch(self, client, doi, mailto=None):
        async with self._limiters["doi"]:
            return await _doi_fetch(client, doi, mailto=mailto)

    async def search_all(self, client, title, cfg):
        tasks = []

        async def run(name, coro_factory):
            async with self._limiters[name]:
                return await coro_factory()

        tasks.append(run("crossref",
                         lambda: crossref.search(client, title, mailto=cfg.mailto)))
        if cfg.use_openalex:
            tasks.append(run("openalex",
                             lambda: openalex.search(client, title,
                                                     api_key=cfg.openalex_key,
                                                     mailto=cfg.mailto)))
        if cfg.use_dblp:
            tasks.append(run("dblp",
                             lambda: dblp.search(client, title, mailto=cfg.mailto)))
        if cfg.use_semantic_scholar:
            tasks.append(run("semantic_scholar",
                             lambda: semantic_scholar.search(
                                 client, title, api_key=cfg.semantic_scholar_key,
                                 mailto=cfg.mailto)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged = []
        for r in results:
            if isinstance(r, Exception):
                logger.debug("某源检索异常: %s", r)
                continue
            merged.extend(r)
        return merged

    async def scholar_fetch(self, query, proxy=None):
        return await asyncio.to_thread(scholar.fetch, query, proxy)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sources_aggregate.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/sources/__init__.py tests/test_sources_aggregate.py
git commit -m "feat: add DefaultSources aggregator with per-source rate limiting"
```

---

## Task 17: CLI 与批量驱动 (cli.py, __main__.py)

**Files:**
- Create: `scholar_bibtex/cli.py`, `scholar_bibtex/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import asyncio

from scholar_bibtex.cli import run_batch, parse_args
from scholar_bibtex.config import Config
from scholar_bibtex.models import Result


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
    inp.write_text("10.1/ok\n10.2/missing\n", encoding="utf-8")
    out = tmp_path / "out.bib"

    src = StubSources({"10.1/ok": "@article{ok,\n title={OK}\n}"})
    cfg = Config.from_env()
    cfg.use_scholar_fallback = False

    asyncio.run(run_batch(str(inp), str(out), cfg=cfg, sources=src))

    text = out.read_text(encoding="utf-8")
    assert "% Query: 10.1/ok" in text
    assert "@article{ok," in text
    assert "% Query: 10.2/missing" in text
    assert "% Failed" in text

    failed = (tmp_path / "out.bib.failed.txt").read_text(encoding="utf-8")
    assert "10.2/missing" in failed


def test_run_batch_resumes_skips_done(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("10.1/ok\n", encoding="utf-8")
    out = tmp_path / "out.bib"
    out.write_text(
        "% Query: 10.1/ok\n@article{ok,\n title={Cached}\n}\n\n", encoding="utf-8")

    # doi_fetch 若被调用会返回新内容;若断点续传生效则不会被调用
    class FailIfCalled(StubSources):
        async def doi_fetch(self, client, doi, mailto=None):
            raise AssertionError("不应重新抓取已完成条目")

    cfg = Config.from_env()
    cfg.use_scholar_fallback = False
    asyncio.run(run_batch(str(inp), str(out), cfg=cfg, sources=FailIfCalled({})))

    text = out.read_text(encoding="utf-8")
    assert "Cached" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

`scholar_bibtex/cli.py`:
```python
import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

import httpx

from .config import Config
from .pipeline import resolve
from .progress import format_entry, load_done
from .sources import DefaultSources

logger = logging.getLogger(__name__)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="scholar_bibtex",
        description="API 优先的批量 BibTeX 获取(DOI/标题 → 权威 BibTeX)",
    )
    p.add_argument("input", help="输入文件,每行一条 DOI 或标题")
    p.add_argument("output", nargs="?", help="输出 .bib(默认 input.bib)")
    p.add_argument("--proxy", "-p", help="代理 host:port")
    p.add_argument("--high", type=float, help="自动采纳的相似度阈值")
    p.add_argument("--low", type=float, help="标记存疑的下限阈值")
    p.add_argument("--concurrency", type=int, help="全局并发上限")
    p.add_argument("--no-openalex", action="store_true")
    p.add_argument("--no-semantic-scholar", action="store_true")
    p.add_argument("--no-dblp", action="store_true")
    p.add_argument("--no-scholar", action="store_true", help="禁用 Scholar 兜底")
    return p.parse_args(argv)


async def run_batch(input_file: str, output_file: str, *, cfg: Config, sources) -> dict:
    with open(input_file, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    done = load_done(output_file)
    todo = [q for q in lines if q not in done]

    sem = asyncio.Semaphore(cfg.concurrency)
    failed = []
    review = []
    success = 0

    async with httpx.AsyncClient() as client:
        async def work(query):
            async with sem:
                return await resolve(query, client=client, sources=sources, cfg=cfg)

        results = await asyncio.gather(*[work(q) for q in todo]) if todo else []

    # 写出:先回写已完成缓存,再写本次结果(crash-safe,不截断)
    with open(output_file, "w", encoding="utf-8") as f:
        for q in lines:
            if q in done:
                f.write(f"% Query: {q}\n{done[q]}\n\n")
        for r in results:
            f.write(format_entry(r))
            if r.ok:
                success += 1
                if r.review:
                    review.append(r.query)
            else:
                failed.append(r.query)

    if failed:
        with open(output_file + ".failed.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(failed) + "\n")

    return {"success": success, "failed": failed, "review": review,
            "skipped": len(done)}


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在: {args.input}")
        sys.exit(1)
    output = args.output or os.path.splitext(args.input)[0] + ".bib"

    cfg = Config.from_env(
        proxy=args.proxy, high=args.high, low=args.low, concurrency=args.concurrency,
    )
    if args.no_openalex:
        cfg.use_openalex = False
    if args.no_semantic_scholar:
        cfg.use_semantic_scholar = False
    if args.no_dblp:
        cfg.use_dblp = False
    if args.no_scholar:
        cfg.use_scholar_fallback = False

    print("📚 Scholar BibTeX (API-first)")
    print(f"📂 输入: {args.input}  →  📄 输出: {output}")

    stats = asyncio.run(run_batch(args.input, output, cfg=cfg, sources=DefaultSources()))

    print(f"\n🎉 完成! 成功 {stats['success']} | "
          f"存疑 {len(stats['review'])} | 失败 {len(stats['failed'])} | "
          f"跳过(已完成) {stats['skipped']}")
    if stats["review"]:
        print("⚠️  存疑(请人工核对):")
        for q in stats["review"][:5]:
            print(f"   • {q}")
    if stats["failed"]:
        print(f"❌ 失败 {len(stats['failed'])} 条,见 {output}.failed.txt")


if __name__ == "__main__":
    main()
```

`scholar_bibtex/__main__.py`:
```python
from .cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scholar_bibtex/cli.py scholar_bibtex/__main__.py tests/test_cli.py
git commit -m "feat: add CLI batch driver with resume and failed-list output"
```

---

## Task 18: 全量测试 + README 更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 跑全量测试**

Run: `pytest -v`
Expected: 全部 PASS(约 40+ 用例)

- [ ] **Step 2: 冒烟测试 import 链**

Run: `python -c "from scholar_bibtex.cli import main; from scholar_bibtex.sources import DefaultSources; print('import ok')"`
Expected: `import ok`

- [ ] **Step 3: 更新 README**

在 `README.md` 顶部"使用"段后追加新用法段落:
```markdown
## 新版(API 优先,推荐)

更快、更准、更一致:DOI 走官方 content negotiation 取权威 BibTeX,标题先消歧到 DOI 再取权威,严格相似度验证并标记存疑,Google Scholar 仅作兜底。

```bash
python -m scholar_bibtex papers.txt [output.bib] [--proxy host:port]
```

可选环境变量:
- `CROSSREF_MAILTO`:进入 Crossref 礼貌池(更高速率),建议设置
- `OPENALEX_API_KEY`:启用 OpenAlex 源(2026-02 起必需;未设则自动跳过)
- `SEMANTIC_SCHOLAR_API_KEY`:可选,提升 Semantic Scholar 速率

输出每条带来源与置信标注;低置信匹配标 `% REVIEW` 需人工核对;失败条目写入 `<output>.failed.txt`。

旧版纯 Google Scholar 抓取仍保留:`python get_google_scholar_bibtex.py papers.txt`。
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document API-first CLI usage"
```

---

## Self-Review(计划编写者已核对)

- **Spec 覆盖**:§3 管线→Task15;§4 源链→Task8–13,16;§5 匹配→Task3;§6 限流→Task6,16;§7 输出→Task5,17;§8 模块→各 Task;§9 依赖→Task0;§10 配置→Task14;§11 兼容→Task13(复用 Selenium)、Task17(`__main__`、参数兼容)、Task5(`% Query` 续传);§12 错误→各源 try/except + Task15 降级;§13 测试→每 Task 含 TDD。
- **占位符**:无 TBD/TODO;每步含完整代码与命令。
- **类型一致**:`Candidate`/`Result` 字段在 models 定义后,matching/pipeline/progress/sources 引用一致;`sources` 注入对象在 Task15 定义协议、Task16 实现(`doi_fetch`/`search_all`/`scholar_fetch` 同名)、Task17 stub 同签名。
- **风险**:`ratelimit` 时间断言用宽松下界避免 flaky;Scholar 兜底懒导入,测试不需 selenium;OpenAlex 无 key 自动跳过。
