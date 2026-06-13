from scholar_bibtex.matching import (
    normalize_title, score_titles, verdict, pick_best, is_annotation_doi,
)
from scholar_bibtex.models import Candidate


def test_normalize_lowercases_and_strips_punct():
    assert normalize_title("Hello, World! A Study.") == "hello world a study"


def test_exact_match_scores_100():
    assert score_titles("Deep Learning", "Deep Learning") == 100


def test_word_order_matters_for_titles():
    # 标题顺序敏感:重排词序的不同标题不应判为高分(防"拿错论文")
    s = score_titles("protein design machine learning",
                     "machine learning protein design")
    assert s < 95


def test_reordered_different_paper_not_auto_accepted():
    # 真实回归:"Attention is all you need"(Transformer)vs
    # "Is Attention All You Need?"(另一篇)—— 不能落入 high 自动采纳区
    s = score_titles("Attention is all you need", "Is Attention All You Need?")
    assert s < 95  # 落入存疑或拒绝,而非自动采纳


def test_punctuation_and_case_still_match():
    # 仅大小写/标点差异仍应判为同一标题
    s = score_titles("Attention is all you need", "Attention Is All You Need")
    assert s >= 99


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


def test_is_annotation_doi():
    assert is_annotation_doi("10.3410/f.740477162.793587584")   # F1000
    assert is_annotation_doi("10.1530/ey.19.15.15")             # Bioscientifica Year Book
    assert not is_annotation_doi("10.1126/science.abj8754")     # 真实论文
    assert not is_annotation_doi(None)


def test_pick_best_excludes_annotation_doi_even_at_score_100():
    # 逐字标题的年鉴/评论条目(满分)不能被选中,应让位给真实论文
    title = "Accurate prediction of protein structures using a three-track neural network"
    cands = [
        Candidate(title=title, doi="10.1530/ey.19.15.15", source="crossref"),   # 年鉴评注
        Candidate(title=title, doi="10.1126/science.abj8754", source="crossref"),  # 真实论文
    ]
    best = pick_best(title, cands)
    assert best is not None
    assert best.candidate.doi == "10.1126/science.abj8754"


def test_pick_best_none_when_only_annotation_match():
    # 只有注解条目命中时,宁可返回 None(失败安全)也不拿错
    title = "Some paper title verbatim"
    cands = [Candidate(title=title, doi="10.3410/f.123.456", source="crossref")]
    assert pick_best(title, cands) is None
