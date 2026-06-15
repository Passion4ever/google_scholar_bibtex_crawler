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

# "注解/镜像某论文"的 DOI 注册库:它们逐字复制原文标题(相似度会到 100),
# 但 DOI 指向的是评论/年鉴/转载而非版本-of-record。取其 BibTeX 会拿错东西。
#   10.3410/f.            — F1000 / Faculty Opinions recommendations
#   10.1530/ey.           — Bioscientifica "Year Book" 评注
#   10.55277/researchhub  — ResearchHub 用户转载镜像(非出版商版本)
_ANNOTATION_DOI = re.compile(
    r"^10\.(?:3410/f\.|1530/ey\.|55277/researchhub)", re.IGNORECASE)


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


@dataclass
class Decision:
    """跨源交叉验证后的最终决策。"""
    candidate: Candidate     # 选中的候选(权威 DOI 或原生 bibtex)
    score: float
    confidence: str          # "high" | "review"
    agreement: int           # 有多少个不同的源支持选中的 DOI
    conflict: bool           # 是否存在另一个不同 DOI 也达到 high(同名歧义)
    note: str = ""           # 冲突等的可读说明


def consolidate(
    query_title: str,
    candidates: Sequence[Candidate],
    high: float = HIGH_DEFAULT,
    low: float = LOW_DEFAULT,
    source_priority: Optional[List[str]] = None,
) -> Optional["Decision"]:
    """多源交叉验证:按 DOI 聚合候选,用"多源一致/冲突"调整置信度。

    规则(正确性优先):
      - 多个源给出同一 DOI → 该 DOI 可信度提升(借此救回单源分数偏低的情况)。
      - 选中 DOI 分数 >= high:
          · 若另有一个**不同** DOI 也 >= high 且选中项未被多源印证 → 标记存疑(同名歧义)。
          · 否则 → high。
      - 选中 DOI 分数在 [low, high):
          · 若 >= 2 个源一致 → 升级为 high;否则 → 存疑。
      - 仅有无 DOI 的候选(如 DBLP/S2 原生 bibtex)→ 退回单源 verdict 逻辑。
      - 没有任何 >= low 的候选 → None(失败安全)。
    """
    priority = source_priority or DEFAULT_SOURCE_PRIORITY
    cands = [c for c in candidates if not is_annotation_doi(c.doi)]

    scored = [(score_titles(query_title, c.title), c) for c in cands]
    scored = [(s, c) for s, c in scored if s >= low]
    if not scored:
        return None

    groups: dict = {}   # doi_key -> {"score","cand","sources"}
    no_doi = []         # [(score, cand)] 无 DOI 的候选
    for s, c in scored:
        if c.doi:
            k = c.doi.lower()
            g = groups.get(k)
            if g is None:
                groups[k] = {"score": s, "cand": c, "sources": {c.source}}
            else:
                g["sources"].add(c.source)
                if s > g["score"]:
                    g["score"], g["cand"] = s, c
        else:
            no_doi.append((s, c))

    if not groups:
        no_doi.sort(key=lambda x: -x[0])
        s, c = no_doi[0]
        v = verdict(s, high, low)
        if v == "reject":
            return None
        return Decision(candidate=c, score=s,
                        confidence="high" if v == "high" else "review",
                        agreement=1, conflict=False)

    def gkey(item):
        k, g = item
        try:
            pr = priority.index(g["cand"].source)
        except ValueError:
            pr = len(priority)
        return (-g["score"], -len(g["sources"]), pr)

    ranked = sorted(groups.items(), key=gkey)
    top_key, top = ranked[0]
    agreement = len(top["sources"])
    conflict_keys = [k for k, g in ranked[1:] if g["score"] >= high]
    conflict = bool(conflict_keys)

    if top["score"] >= high:
        confidence = "review" if (conflict and agreement < 2) else "high"
    else:
        confidence = "high" if agreement >= 2 else "review"

    note = ""
    if conflict:
        note = f"标题相同的多个 DOI: {top['cand'].doi} vs " + ", ".join(
            groups[k]["cand"].doi for k in conflict_keys[:2])

    return Decision(candidate=top["cand"], score=top["score"], confidence=confidence,
                    agreement=agreement, conflict=conflict, note=note)


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
