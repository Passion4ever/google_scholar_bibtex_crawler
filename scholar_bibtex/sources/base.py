from typing import Optional

from .. import __version__
from ..ratelimit import TransientError


def USER_AGENT(mailto: Optional[str]) -> str:
    base = f"scholar_bibtex/{__version__}"
    if mailto:
        return f"{base} (mailto:{mailto})"
    return base


def classify_http_error(status: int) -> None:
    """429 / 5xx 抛 TransientError(可重试);其余返回 None。"""
    if status == 429 or 500 <= status < 600:
        raise TransientError(f"HTTP {status}")
    return None
