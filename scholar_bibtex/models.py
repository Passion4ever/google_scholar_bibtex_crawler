from dataclasses import dataclass
from typing import Optional


@dataclass
class Candidate:
    """一个标题查询返回的候选论文。"""
    title: str
    doi: Optional[str] = None
    source: str = ""
    bibtex: Optional[str] = None  # 源若原生提供 BibTeX(如 DBLP/S2)
    year: Optional[int] = None


@dataclass
class Result:
    """一条输入的最终处理结果。"""
    query: str
    bibtex: Optional[str] = None
    doi: Optional[str] = None
    source: str = ""
    confidence: str = ""        # exact-doi | high | review | failed
    match_title: Optional[str] = None
    score: Optional[float] = None
    review: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.bibtex is not None
