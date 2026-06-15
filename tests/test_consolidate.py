from scholar_bibtex.matching import consolidate
from scholar_bibtex.models import Candidate

T = "Deep learning for protein structure prediction"


def test_none_when_no_candidates():
    assert consolidate(T, []) is None


def test_none_when_all_below_low():
    cands = [Candidate(title="Totally unrelated cats and dogs", doi="10.1/x", source="crossref")]
    assert consolidate(T, cands) is None


def test_single_source_exact_is_high():
    cands = [Candidate(title=T, doi="10.1/a", source="crossref")]
    d = consolidate(T, cands)
    assert d.confidence == "high"
    assert d.candidate.doi == "10.1/a"
    assert d.agreement == 1
    assert d.conflict is False


def test_multi_source_agreement_on_same_doi_upgrades_borderline():
    # 单源时分数落在存疑区,但两个源给同一 DOI → 升级为 high
    near = T + " using neural nets"   # 略有差异,分数 < high
    cands = [
        Candidate(title=near, doi="10.1/same", source="crossref"),
        Candidate(title=near, doi="10.1/same", source="openalex"),
    ]
    d = consolidate(T, cands, high=99, low=60)
    assert d.candidate.doi == "10.1/same"
    assert d.agreement == 2
    assert d.confidence == "high"   # 多源一致补偿了中等分数


def test_borderline_single_source_stays_review():
    near = T + " using neural nets"
    cands = [Candidate(title=near, doi="10.1/one", source="crossref")]
    d = consolidate(T, cands, high=99, low=60)
    assert d.agreement == 1
    assert d.confidence == "review"


def test_conflicting_high_dois_flag_review():
    # 两个不同 DOI 都逐字匹配(同名不同篇)→ 存疑,不静默选一个
    cands = [
        Candidate(title=T, doi="10.1/paperA", source="crossref"),
        Candidate(title=T, doi="10.2/paperB", source="openalex"),
    ]
    d = consolidate(T, cands)
    assert d.confidence == "review"
    assert d.conflict is True
    assert "10.1/paperA" in d.note and "10.2/paperB" in d.note


def test_corroborated_top_wins_over_conflict():
    # 选中 DOI 被两个源印证,即使另有一个不同高分 DOI,也判 high
    cands = [
        Candidate(title=T, doi="10.1/real", source="crossref"),
        Candidate(title=T, doi="10.1/real", source="openalex"),
        Candidate(title=T, doi="10.2/other", source="dblp"),
    ]
    d = consolidate(T, cands)
    assert d.candidate.doi == "10.1/real"
    assert d.agreement == 2
    assert d.confidence == "high"


def test_annotation_doi_excluded():
    cands = [
        Candidate(title=T, doi="10.3410/f.123.456", source="crossref"),  # F1000 注解
        Candidate(title=T, doi="10.9/real", source="crossref"),
    ]
    d = consolidate(T, cands)
    assert d.candidate.doi == "10.9/real"


def test_no_doi_candidate_uses_native_path():
    cands = [Candidate(title=T, doi=None, source="dblp", bibtex="@inproceedings{x,}")]
    d = consolidate(T, cands)
    assert d.confidence == "high"
    assert d.candidate.bibtex.startswith("@")
