from scholar_bibtex.normalize import normalize_bibtex, normalize_authors, make_citekey


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
    assert out.index("title") < out.index("author")


def test_normalize_bad_input_returns_original():
    junk = "this is not bibtex at all"
    assert normalize_bibtex(junk) == junk


# doi.org 的 BibTeX 用裸全月份名 month=July,带 common_strings 解析会抛 UndefinedString
DOI_ORG_STYLE = (
    "@article{Watson_2023, title={De novo design}, volume={620}, "
    "author={Baker, David}, year={2023}, month=July, pages={1089--1100} }"
)


def test_normalize_handles_bare_month_name():
    out = normalize_bibtex(DOI_ORG_STYLE)
    assert "\n" in out
    assert out.index("title") < out.index("author")
    assert "De novo design" in out


# --- 作者姓名顺序统一(姓在前,与 Google Scholar 一致)---

def test_normalize_authors_reorders_given_first_to_last_first():
    assert normalize_authors("Joseph L. Watson and David Juergens") == \
        "Watson, Joseph L. and Juergens, David"


def test_normalize_authors_idempotent_on_comma_form():
    s = "Watson, Joseph L. and Juergens, David"
    assert normalize_authors(s) == s


def test_normalize_authors_preserves_particles_and_compounds():
    # 介词/复姓/变音不被改坏
    assert normalize_authors("van Grondelle, R.") == "van Grondelle, R."
    assert normalize_authors("dos Santos Costa, Allan") == "dos Santos Costa, Allan"
    assert normalize_authors("Torres, Susana Vázquez") == "Torres, Susana Vázquez"


def test_normalize_bibtex_enforces_author_order():
    raw = "@article{x, title={T}, author={John Jumper and Demis Hassabis}, year={2021}}"
    out = normalize_bibtex(raw)
    assert "Jumper, John" in out
    assert "Hassabis, Demis" in out


# --- 引用键统一 ---

def test_make_citekey_scheme():
    entry = {"author": "Watson, Joseph L. and Baker, David",
             "year": "2023", "title": "De novo design of protein structure"}
    assert make_citekey(entry) == "watson2023novo"  # 跳过停用词 "de"


def test_make_citekey_fallback_to_existing_id():
    entry = {"ID": "fallback_key", "title": "X"}  # 无 author/year
    assert make_citekey(entry) == "fallback_key"


def test_normalize_bibtex_unifies_key():
    raw = ("@misc{https://doi.org/10.48550/arxiv.2409.08022, "
           "title={Some Cool Method}, author={Jane Doe}, year={2024}}")
    out = normalize_bibtex(raw)
    assert out.startswith("@misc{doe2024some") or "{doe2024some" in out
    assert "https://doi.org" not in out.split("\n")[0]  # 网址不再当键
