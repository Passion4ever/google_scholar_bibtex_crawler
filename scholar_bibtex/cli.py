import argparse
import asyncio
import logging
import os
import sys

import httpx

from .config import Config
from .pipeline import resolve
from .progress import format_entry, load_done
from .sources import DefaultSources

logger = logging.getLogger(__name__)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="scholar_bibtex",
        description="API 优先的批量 BibTeX 获取(DOI/标题 → 权威 BibTeX)",
    )
    p.add_argument("input", help="输入文件,每行一条 DOI 或标题")
    p.add_argument("output", nargs="?", help="输出 .bib(默认 input.bib)")
    p.add_argument("--proxy", "-p", help="代理 host:port")
    p.add_argument("--high", type=float, help="自动采纳的相似度阈值")
    p.add_argument("--low", type=float, help="标记存疑的下限阈值")
    p.add_argument("--concurrency", type=int, help="全局并发上限")
    p.add_argument("--no-openalex", action="store_true")
    p.add_argument("--no-semantic-scholar", action="store_true")
    p.add_argument("--no-dblp", action="store_true")
    p.add_argument("--no-scholar", action="store_true", help="禁用 Scholar 兜底")
    return p.parse_args(argv)


async def run_batch(input_file: str, output_file: str, *, cfg: Config, sources) -> dict:
    with open(input_file, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f
                 if ln.strip() and not ln.lstrip().startswith("#")]

    done = load_done(output_file)
    todo = [q for q in lines if q not in done]

    sem = asyncio.Semaphore(cfg.concurrency)
    failed = []
    review = []
    success = 0

    async with httpx.AsyncClient() as client:
        async def work(query):
            async with sem:
                return await resolve(query, client=client, sources=sources, cfg=cfg)

        results = await asyncio.gather(*[work(q) for q in todo]) if todo else []

    # 写出:先回写已完成缓存,再写本次结果(crash-safe,不截断)
    with open(output_file, "w", encoding="utf-8") as f:
        for q in lines:
            if q in done:
                f.write(f"% Query: {q}\n{done[q]}\n\n")
        for r in results:
            f.write(format_entry(r))
            if r.ok:
                success += 1
                if r.review:
                    review.append(r.query)
            else:
                failed.append(r.query)

    if failed:
        with open(output_file + ".failed.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(failed) + "\n")

    return {"success": success, "failed": failed, "review": review,
            "skipped": len(done)}


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在: {args.input}")
        sys.exit(1)
    output = args.output or os.path.splitext(args.input)[0] + ".bib"

    cfg = Config.from_env(
        proxy=args.proxy, high=args.high, low=args.low, concurrency=args.concurrency,
    )
    if args.no_openalex:
        cfg.use_openalex = False
    if args.no_semantic_scholar:
        cfg.use_semantic_scholar = False
    if args.no_dblp:
        cfg.use_dblp = False
    if args.no_scholar:
        cfg.use_scholar_fallback = False

    print("📚 Scholar BibTeX (API-first)")
    print(f"📂 输入: {args.input}  →  📄 输出: {output}")

    stats = asyncio.run(run_batch(args.input, output, cfg=cfg, sources=DefaultSources()))

    print(f"\n🎉 完成! 成功 {stats['success']} | "
          f"存疑 {len(stats['review'])} | 失败 {len(stats['failed'])} | "
          f"跳过(已完成) {stats['skipped']}")
    if stats["review"]:
        print("⚠️  存疑(请人工核对):")
        for q in stats["review"][:5]:
            print(f"   • {q}")
    if stats["failed"]:
        print(f"❌ 失败 {len(stats['failed'])} 条,见 {output}.failed.txt")


if __name__ == "__main__":
    main()
