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

# "注解某论文"的 DOI 注册库:它们逐字复制原文标题(相似度会到 100),
# 但 DOI 指向的是评论/年鉴条目而非论文本身。取其 BibTeX 会拿错东西。
#   10.3410/f.  — F1000 / Faculty Opinions recommendations
#   10.1530/ey. — Bioscientifica "Year Book" 评注
_ANNOTATION_DOI = re.compile(r"^10\.(?:3410/f\.|1530/ey\.)", re.IGNORECASE)


def is_annotation_doi(doi) -> bool:
    """该 DOI 是否为"注解某论文"的条目(应排除,避免拿错)。"""
    return bool(doi and _ANNOTATION_DOI.match(doi))


def normalize_title(title: str) -> str:
    t = title.lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def score_titles(a: str, b: str) -> float:
    """标题相似度。用顺序敏感的 ratio,而非 token_sort_ratio。

    标题是有序的:'Attention is all you need' 与 'Is Attention All You
    Need?' 是不同论文,token_sort 会把它们判为 100(词序无关),造成
    严重的"拿错论文"。ratio 对前者给 ~88,落入存疑区间而非自动采纳。
    (作者姓名顺序/缩写的不一致是输出问题,已由权威 DOI 源解决,与标题匹配无关。)
    """
    return fuzz.ratio(normalize_title(a), normalize_title(b))


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

    # 剔除"注解某论文"的 DOI 条目(逐字标题会骗到满分,但取回的是评论)
    candidates = [c for c in candidates if not is_annotation_doi(c.doi)]

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
