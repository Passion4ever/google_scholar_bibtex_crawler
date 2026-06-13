import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bparser import BibTexParser

_DISPLAY_ORDER = (
    "title", "author", "journal", "booktitle", "year",
    "volume", "number", "pages", "publisher", "doi", "url",
)


def normalize_bibtex(raw: str) -> str:
    """解析后用固定字段顺序/缩进重新输出;解析失败原样返回。"""
    try:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.loads(raw, parser=parser)
        if not db.entries:
            return raw
        writer = BibTexWriter()
        writer.indent = "  "
        writer.order_entries_by = None  # 保持输入顺序
        writer.display_order = _DISPLAY_ORDER
        return bibtexparser.dumps(db, writer=writer).strip()
    except Exception:
        return raw
