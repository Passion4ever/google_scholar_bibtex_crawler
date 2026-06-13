import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    mailto: Optional[str] = None
    openalex_key: Optional[str] = None
    semantic_scholar_key: Optional[str] = None
    proxy: Optional[str] = None
    high: float = 95.0
    low: float = 85.0
    concurrency: int = 8
    use_openalex: bool = True
    use_semantic_scholar: bool = True
    use_dblp: bool = True
    use_scholar_fallback: bool = True

    @classmethod
    def from_env(cls, **overrides) -> "Config":
        base = dict(
            mailto=os.environ.get("CROSSREF_MAILTO") or None,
            openalex_key=os.environ.get("OPENALEX_API_KEY") or None,
            semantic_scholar_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None,
        )
        base.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**base)
