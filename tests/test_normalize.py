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
