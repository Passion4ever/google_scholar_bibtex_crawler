import re
from typing import Tuple

_DOI_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$",
    re.IGNORECASE,
)


def classify(query: str) -> Tuple[str, str]:
    """判定输入是 DOI 还是标题。

    返回 ("doi", 规范化DOI) 或 ("title", 去空白标题)。
    """
    q = query.strip()
    m = _DOI_RE.match(q)
    if m:
        return ("doi", m.group(1))
    return ("title", q)
