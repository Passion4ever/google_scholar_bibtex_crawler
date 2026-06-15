import re

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import splitname

_DISPLAY_ORDER = (
    "title", "author", "journal", "booktitle", "year",
    "volume", "number", "pages", "publisher", "doi", "url",
)

# 引用键里跳过的标题停用词(取第一个有意义的词,与 Google Scholar 习惯靠拢)
_STOPWORDS = {
    "a", "an", "the", "de", "of", "on", "in", "for", "and", "with",
    "to", "from", "by", "via", "using",
}


def _format_name(name: str) -> str:
    """把单个作者名规整为 `姓, 名`(姓在前,与 Google Scholar 一致)。

    用 BibTeX 的姓名解析规则:无逗号的 `名 姓` 会被翻成 `姓, 名`;
    已是 `姓, 名` 则幂等;介词/复姓/变音保持不变。
    """
    name = name.strip()
    if not name:
        return name
    try:
        p = splitname(name)
    except Exception:
        return name
    last = " ".join(p.get("von", []) + p.get("last", []))
    first = " ".join(p.get("first", []))
    jr = " ".join(p.get("jr", []))
    if not last:
        return name  # 单 token / 解析不出姓,原样保留(如纯 CJK)
    out = last
    if jr:
        out += ", " + jr
    if first:
        out += ", " + first
    return out


_VENUE_RE = re.compile(r"(?i)[,{]\s*(journal|booktitle)\s*=")


def has_venue(bibtex: str) -> bool:
    """BibTeX 是否已有 journal/booktitle(venue)字段。"""
    return bool(_VENUE_RE.search(bibtex))


def inject_journal(bibtex: str, venue: str) -> str:
    """给缺 venue 的条目补上 journal={venue}(已有则不动)。"""
    if not venue or has_venue(bibtex):
        return bibtex
    idx = bibtex.rfind("}")
    if idx == -1:
        return bibtex
    head = bibtex[:idx].rstrip().rstrip(",")
    return f"{head}, journal={{{venue}}} {bibtex[idx:]}"


def normalize_authors(field: str) -> str:
    """把作者字段(以 ' and ' 分隔)里每个名字统一成 `姓, 名`。"""
    parts = re.split(r"\s+and\s+", field.strip())
    return " and ".join(_format_name(p) for p in parts if p.strip())


def make_citekey(entry: dict) -> str:
    """生成统一的引用键 lastnameYYYYword(全小写),失败则回退原 ID。"""
    authors = entry.get("author", "")
    first_author = re.split(r"\s+and\s+", authors)[0] if authors else ""
    surname = ""
    if first_author:
        try:
            p = splitname(first_author)
            tokens = p.get("last", []) or p.get("von", [])
            surname = re.sub(r"[^A-Za-z]", "", "".join(tokens)).lower()
        except Exception:
            surname = ""
    year = re.sub(r"[^0-9]", "", entry.get("year", ""))[:4]
    words = re.findall(r"[A-Za-z]+", entry.get("title", "").lower())
    word = next((w for w in words if w not in _STOPWORDS and len(w) > 1), "")
    key = f"{surname}{year}{word}"
    return key if surname and year else entry.get("ID", key) or entry.get("ID", "")


def normalize_bibtex(raw: str) -> str:
    """解析后统一格式:固定字段顺序、缩进、作者 `姓,名` 顺序、引用键。

    解析失败原样返回。
    """
    try:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        # 不解析字符串宏:doi.org 的 BibTeX 用裸 month=July,解析宏会抛 UndefinedString
        parser.interpolate_strings = False
        db = bibtexparser.loads(raw, parser=parser)
        if not db.entries:
            return raw
        for entry in db.entries:
            if entry.get("author"):
                entry["author"] = normalize_authors(entry["author"])
            if entry.get("editor"):
                entry["editor"] = normalize_authors(entry["editor"])
            entry["ID"] = make_citekey(entry)
        writer = BibTexWriter()
        writer.indent = "  "
        writer.order_entries_by = None
        writer.display_order = _DISPLAY_ORDER
        return bibtexparser.dumps(db, writer=writer).strip()
    except Exception:
        return raw
