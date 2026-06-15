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
