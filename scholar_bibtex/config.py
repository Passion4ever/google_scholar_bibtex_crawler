import os
from dataclasses import dataclass
from typing import Dict, Optional


def _load_dotenv(path: str) -> Dict[str, str]:
    """极简 .env 解析:KEY=VALUE,忽略空行/注释,去引号与空白。无依赖。"""
    values: Dict[str, str] = {}
    if not path or not os.path.exists(path):
        return values
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'").strip()
                if key:
                    values[key] = val
    except (IOError, OSError):
        pass
    return values


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

    @classmethod
    def from_env(cls, dotenv_path: str = ".env", **overrides) -> "Config":
        # 优先级:真实环境变量 > .env 文件
        dot = _load_dotenv(dotenv_path)

        def get(name):
            return os.environ.get(name) or dot.get(name) or None

        base = dict(
            mailto=get("CROSSREF_MAILTO"),
            openalex_key=get("OPENALEX_API_KEY"),
            semantic_scholar_key=get("SEMANTIC_SCHOLAR_API_KEY"),
        )
        base.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**base)
