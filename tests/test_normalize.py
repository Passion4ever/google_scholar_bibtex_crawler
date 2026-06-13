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


# 真实世界回归:doi.org/Crossref 返回的 BibTeX 用裸的全月份名(month=July),
# 这会让带 common_strings 的解析器抛 UndefinedString。归一化必须能处理。
DOI_ORG_STYLE = (
    "@article{Watson_2023, title={De novo design}, volume={620}, "
    "author={Baker, David}, year={2023}, month=July, pages={1089--1100} }"
)


def test_normalize_handles_bare_month_name():
    out = normalize_bibtex(DOI_ORG_STYLE)
    # 应被重新格式化为多行(缩进),而非原样返回单行
    assert "\n" in out
    assert out.index("title") < out.index("author")
    assert "De novo design" in out
