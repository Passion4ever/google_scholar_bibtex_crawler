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
