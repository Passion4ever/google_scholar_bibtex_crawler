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
