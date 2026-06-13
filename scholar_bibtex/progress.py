import logging
import os
from typing import Dict

from .models import Result

logger = logging.getLogger(__name__)


def load_done(output_file: str) -> Dict[str, str]:
    """解析已有输出,返回 {query: bibtex},仅含取到 @ 内容的成功条目。

    失败/无内容条目不计入,以便断点续传时重试。
    """
    done: Dict[str, str] = {}
    if not os.path.exists(output_file):
        return done
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError, UnicodeDecodeError) as e:
        logger.warning("读取进度文件失败: %s", e)
        return done

    current = None
    buffer = []

    def flush():
        if current is not None:
            block = "\n".join(buffer).strip()
            # 去掉块内以 % 开头的注释行后,看是否有 @ 实体
            body = "\n".join(
                ln for ln in block.splitlines() if not ln.lstrip().startswith("%")
            ).strip()
            if body.startswith("@"):
                done[current] = body

    for line in content.splitlines():
        if line.startswith("% Query:"):
            flush()
            current = line.replace("% Query:", "").strip()
            buffer = []
        else:
            buffer.append(line)
    flush()
    return done


def format_entry(result: Result) -> str:
    """把一条 Result 渲染为带溯源注释的 .bib 文本块(末尾含空行)。"""
    lines = [f"% Query: {result.query}"]
    if result.ok:
        if result.review:
            lines.append(
                f'% REVIEW: 匹配到 "{result.match_title}" '
                f"score={result.score:.0f} via {result.source} —— 请人工核对"
            )
        else:
            conf = result.confidence
            detail = f"% Source: {result.source} | Confidence: {conf}"
            if result.match_title and result.score is not None:
                detail += f' | Match: "{result.match_title}" score={result.score:.0f}'
            lines.append(detail)
        lines.append(result.bibtex)
    else:
        lines.append("% Failed")
        if result.error:
            lines.append(f"% Reason: {result.error}")
    return "\n".join(lines) + "\n\n"
