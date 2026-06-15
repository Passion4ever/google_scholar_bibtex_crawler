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
