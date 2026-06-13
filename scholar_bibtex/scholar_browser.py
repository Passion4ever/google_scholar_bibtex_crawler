"""基于 nodriver 的 Google Scholar BibTeX 抓取器(浏览器版,高准确度优先)。

为什么用 nodriver 而非 undetected-chromedriver:
- nodriver 通过 CDP 直连浏览器,不需要 ChromeDriver,**没有版本匹配问题**
  (uc 3.5.5 已停更,驱动版本对不上新版 Chrome 就崩)。
- 更隐身,新 IP 上验证码更少。

注意:Google Scholar 的拦截是按 IP/行为来的,任何工具都躲不开已被标记的 IP。
遇到验证码时本脚本会暂停,等你在浏览器里手动完成后按 Enter 继续;cookie 会持久化,
解一次后续会少很多。

用法:
    python -m scholar_bibtex.scholar_browser <input.txt> [output.bib]
"""
import argparse
import asyncio
import os
import sys
from typing import Optional

from .normalize import normalize_bibtex
from .progress import load_done

try:
    import nodriver
except ImportError:
    nodriver = None

COOKIE_FILE = ".google_scholar_nodriver_cookies.dat"
RESULT_SELECTOR = ".gs_r.gs_or.gs_scl"
CITE_SELECTOR = "a.gs_or_cit"

# 拦截/验证码信号(出现在页面 URL 或正文)
_BLOCK_MARKERS = ("/sorry/", "unusual traffic", "not a robot", "recaptcha")


async def _count_results(page) -> int:
    try:
        return await page.evaluate(
            f"document.querySelectorAll('{RESULT_SELECTOR}').length")
    except Exception:
        return 0


def looks_blocked(url: str, html: str) -> bool:
    """纯函数:由 URL/正文判断是否被拦截(便于单测)。"""
    if "/sorry/" in (url or "").lower():
        return True
    return any(m in (html or "").lower() for m in _BLOCK_MARKERS)


async def is_blocked(page) -> bool:
    """搜索页是否被拦截:有结果即未拦截;否则按 URL/正文特征判断。"""
    if await _count_results(page) > 0:
        return False
    try:
        url = await page.evaluate("location.href") or ""
    except Exception:
        url = ""
    try:
        html = await page.get_content() or ""
    except Exception:
        html = ""
    return looks_blocked(url, html)


async def _wait_for_human(prompt: str):
    """异步等待用户在终端按 Enter(不阻塞事件循环)。"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input, prompt)


async def _solve_captcha_then_reload(browser, page, url):
    print("\n" + "─" * 50)
    print("🤖 检测到 Google Scholar 验证码/拦截")
    print("   请在弹出的浏览器窗口里手动完成验证,然后回到这里按 Enter")
    print("─" * 50)
    await _wait_for_human("完成后按 Enter 继续... ")
    try:
        await browser.cookies.save(COOKIE_FILE)
    except Exception:
        pass
    return await browser.get(url)


async def fetch_one(browser, query: str) -> Optional[str]:
    """搜索一条 → 点引用 → 取 BibTeX。失败返回 None。"""
    url = "https://scholar.google.com/scholar?q=" + query.replace(" ", "+")
    page = await browser.get(url)
    await asyncio.sleep(3)

    if await is_blocked(page):
        page = await _solve_captcha_then_reload(browser, page, url)
        await asyncio.sleep(3)
        if await is_blocked(page):
            return None

    # 第一条结果的"引用"按钮
    try:
        cite = await page.select(CITE_SELECTOR, timeout=10)
    except Exception:
        return None
    if not cite:
        return None
    await cite.click()
    await asyncio.sleep(2)

    # 引用弹窗里的 BibTeX 链接
    try:
        bib_link = await page.find("BibTeX", best_match=True, timeout=10)
    except Exception:
        return None
    if not bib_link:
        return None
    href = await bib_link.get_attribute("href")
    if not href:
        return None

    bib_page = await browser.get(href)
    await asyncio.sleep(2)
    if await is_blocked(bib_page):
        bib_page = await _solve_captcha_then_reload(browser, bib_page, href)
        await asyncio.sleep(2)
    try:
        text = await bib_page.evaluate(
            "(document.querySelector('pre')||document.body).innerText")
    except Exception:
        return None
    text = (text or "").strip()
    return text if "@" in text else None


async def run(input_file: str, output_file: str):
    with open(input_file, "r", encoding="utf-8") as f:
        queries = [ln.strip() for ln in f
                   if ln.strip() and not ln.lstrip().startswith("#")]

    done = load_done(output_file)
    todo = [q for q in queries if q not in done]
    if done:
        print(f"⏩ 断点续传:跳过已完成 {len(done)} 条,待处理 {len(todo)} 条")

    browser = await nodriver.start(headless=False)
    if os.path.exists(COOKIE_FILE):
        try:
            await browser.cookies.load(COOKIE_FILE)
        except Exception:
            pass

    success, failed = 0, []
    # 先回写已完成缓存(crash-safe),再追加新结果
    with open(output_file, "w", encoding="utf-8") as f:
        for q in queries:
            if q in done:
                f.write(f"% Query: {q}\n{done[q]}\n\n")
        f.flush()
        for idx, q in enumerate(todo, 1):
            disp = q if len(q) <= 55 else q[:55] + "…"
            print(f"\n🔍 [{idx}/{len(todo)}] {disp}")
            f.write(f"% Query: {q}\n")
            f.flush()
            try:
                bib = await fetch_one(browser, q)
            except Exception as e:
                print(f"   异常: {e}")
                bib = None
            if bib:
                f.write(normalize_bibtex(bib) + "\n\n")
                success += 1
                print("   ✅ 成功")
            else:
                f.write("% Failed\n\n")
                failed.append(q)
                print("   ❌ 失败")
            f.flush()
            await asyncio.sleep(5)  # 礼貌延迟,降低被封概率

    try:
        await browser.cookies.save(COOKIE_FILE)
    except Exception:
        pass
    browser.stop()

    print(f"\n🎉 完成! 成功 {success} | 失败 {len(failed)} | 跳过 {len(done)}")
    if failed:
        with open(output_file + ".failed.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(failed) + "\n")
        print(f"❌ 失败 {len(failed)} 条,见 {output_file}.failed.txt")


def main(argv=None):
    if nodriver is None:
        print("错误: 请先安装 nodriver  →  pip install nodriver")
        sys.exit(1)
    p = argparse.ArgumentParser(
        prog="scholar_bibtex.scholar_browser",
        description="基于 nodriver 的 Google Scholar BibTeX 抓取(浏览器版)")
    p.add_argument("input", help="输入文件,每行一条 DOI 或标题")
    p.add_argument("output", nargs="?", help="输出 .bib(默认 input.bib)")
    args = p.parse_args(argv)
    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在: {args.input}")
        sys.exit(1)
    output = args.output or os.path.splitext(args.input)[0] + ".bib"
    print("📚 Google Scholar BibTeX (nodriver 浏览器版)")
    print(f"📂 输入: {args.input}  →  📄 输出: {output}\n")
    nodriver.loop().run_until_complete(run(args.input, output))


if __name__ == "__main__":
    main()
