"""
Google Scholar BibTeX Crawler

自动从 Google Scholar 搜索论文并提取 BibTeX 引用信息。

安装依赖:
    pip install undetected-chromedriver selenium

使用方法:
    python get_google_scholar_bibtex.py <input.txt> [output.bib] [--proxy HOST:PORT]
"""

import os
import sys
import time
import random
import json
import logging
import argparse
from urllib.parse import quote_plus

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import undetected_chromedriver as uc
except ImportError:
    print("错误: 请先安装 undetected-chromedriver")
    print("运行: pip install undetected-chromedriver")
    sys.exit(1)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 配置
COOKIE_FILE = ".google_scholar_cookies.json"
MIN_DELAY = 5
MAX_DELAY = 10


def random_delay(min_sec=MIN_DELAY, max_sec=MAX_DELAY):
    """随机延迟"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def _detect_chrome_major():
    """探测本机 Chrome 主版本号(用于匹配 ChromeDriver,避免版本不一致报错)。"""
    import subprocess
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "google-chrome", "google-chrome-stable", "chromium", "chrome",   # Linux/PATH
    ]
    for path in candidates:
        try:
            out = subprocess.check_output([path, "--version"], text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        import re
        m = re.search(r"(\d+)\.\d+", out)
        if m:
            return int(m.group(1))
    return None


def _create_selenium_browser(proxy=None):
    """标准 Selenium 兜底(Selenium Manager 自动匹配驱动,兼容新版 Chrome)。

    比 undetected-chromedriver 更易被 Google Scholar 检测,但能稳定启动。
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    o = Options()
    o.add_argument('--no-sandbox')
    o.add_argument('--disable-dev-shm-usage')
    o.add_argument('--window-size=1920,1080')
    o.add_argument('--lang=en-US')
    o.add_argument('--disable-blink-features=AutomationControlled')
    o.add_experimental_option('excludeSwitches', ['enable-automation'])
    o.add_experimental_option('useAutomationExtension', False)
    if proxy:
        o.add_argument(f'--proxy-server={proxy}')
    driver = webdriver.Chrome(options=o)
    try:  # 抹掉 navigator.webdriver,稍微降低被识别概率
        driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument',
            {'source': "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
    except Exception:
        pass
    return driver


def create_browser(proxy=None):
    """创建浏览器:优先 undetected-chromedriver,失败则回退标准 Selenium。"""
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')
    version = _detect_chrome_major()
    if version:
        logger.debug("检测到 Chrome 主版本: %s", version)
    try:
        return uc.Chrome(options=options, version_main=version)
    except Exception as e:
        logger.warning("undetected-chromedriver 启动失败(%s);回退到标准 Selenium", e)
        return _create_selenium_browser(proxy)


def save_cookies(browser):
    """保存 Cookies 到 JSON 文件"""
    try:
        cookies = browser.get_cookies()
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
    except (IOError, OSError) as e:
        logger.warning(f"保存 Cookies 失败: {e}")
    except Exception as e:
        logger.warning(f"保存 Cookies 时发生未知错误: {e}")


def load_cookies(browser):
    """从 JSON 文件加载 Cookies"""
    if not os.path.exists(COOKIE_FILE):
        return
    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
            for cookie in cookies:
                try:
                    browser.add_cookie(cookie)
                except (KeyError, TypeError) as e:
                    logger.debug(f"跳过无效 Cookie: {e}")
    except json.JSONDecodeError as e:
        logger.warning(f"Cookie 文件格式错误: {e}")
    except (IOError, OSError) as e:
        logger.warning(f"加载 Cookies 失败: {e}")


def check_captcha(browser):
    """检测验证码"""
    try:
        page = browser.page_source.lower()
        indicators = ["captcha", "unusual traffic", "not a robot", "sorry"]
        return any(x in page for x in indicators) or "sorry" in browser.current_url.lower()
    except Exception as e:
        logger.debug(f"检测验证码时出错: {e}")
        return False


def wait_for_captcha(browser):
    """等待用户解决验证码"""
    print("\n" + "─" * 50)
    print("🤖 检测到验证码！请在浏览器中完成验证")
    print("   完成后按 Enter 继续...")
    print("─" * 50)
    input()
    save_cookies(browser)
    random_delay(2, 4)


def extract_title(text):
    """从引用文本提取标题"""
    text = text.strip()
    for sep in ['. ', ' et al. ']:
        if sep in text:
            parts = text.split(sep)
            if len(parts) >= 2:
                title = parts[1].split('. ')[0].strip()
                if len(title) > 10:
                    return title
    return text[:150]


def get_bibtex(browser, wait, query):
    """搜索并获取 BibTeX"""
    search_query = extract_title(query)
    search_url = f"https://scholar.google.com/scholar?q={quote_plus(search_query)}"

    try:
        browser.get(search_url)
        random_delay(3, 5)

        if check_captcha(browser):
            wait_for_captcha(browser)
            browser.get(search_url)
            random_delay(3, 5)

        # 等待搜索结果
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".gs_r.gs_or.gs_scl")))
        except TimeoutException:
            return None

        # 点击引用按钮（使用 JS 点击，避免最小化窗口时失败）
        try:
            cite_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".gs_or_cit.gs_or_btn.gs_nph")))
            browser.execute_script("arguments[0].click();", cite_btn)
            random_delay(1, 2)
        except TimeoutException:
            return None

        # 获取 BibTeX 链接（使用 presence 而非 clickable，避免最小化窗口时失败）
        try:
            bibtex_link = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "BibTeX")))
            bibtex_url = bibtex_link.get_attribute("href")
        except TimeoutException:
            return None

        if not bibtex_url:
            return None

        browser.get(bibtex_url)
        random_delay(1, 2)

        if check_captcha(browser):
            wait_for_captcha(browser)
            browser.get(bibtex_url)
            random_delay(1, 2)

        # 获取 BibTeX 内容
        try:
            pre = wait.until(EC.presence_of_element_located((By.TAG_NAME, "pre")))
            text = pre.text.strip()
            if '@' in text:
                return text
        except TimeoutException:
            logger.debug("未找到 <pre> 标签，尝试备用方案")

        # 备用：从 body 获取
        try:
            text = browser.find_element(By.TAG_NAME, "body").text.strip()
            if '@' in text and len(text) < 2000:
                return text
        except Exception as e:
            logger.debug(f"备用方案获取 BibTeX 失败: {e}")

        return None

    except Exception as e:
        print(f"  异常: {e}")
        return None


def load_progress(output_file):
    """加载已成功处理的记录，返回 {query: bibtex} 字典。

    只有真正取到 BibTeX 的条目才算完成；标记为 `% Failed` 的条目不计入，
    以便断点续传时重新尝试。
    """
    done = {}
    if not os.path.exists(output_file):
        return done
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, OSError) as e:
        logger.warning(f"读取进度文件失败: {e}")
        return done
    except UnicodeDecodeError as e:
        logger.warning(f"进度文件编码错误: {e}")
        return done

    # 按 `% Query:` 切分成块，块内含 BibTeX（以 @ 开头）才算成功
    current_query = None
    buffer = []
    for line in content.splitlines():
        if line.startswith('% Query:'):
            block = "\n".join(buffer).strip()
            if current_query is not None and block.startswith('@'):
                done[current_query] = block
            current_query = line.replace('% Query:', '').strip()
            buffer = []
        else:
            buffer.append(line)
    block = "\n".join(buffer).strip()
    if current_query is not None and block.startswith('@'):
        done[current_query] = block
    return done


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='自动从 Google Scholar 提取 BibTeX 引用信息'
    )
    parser.add_argument('input', help='输入文件，每行一条论文信息')
    parser.add_argument('output', nargs='?', help='输出文件 (默认: input.bib)')
    parser.add_argument('--proxy', '-p', help='代理服务器 (如: 127.0.0.1:7890)')
    return parser.parse_args()


def main():
    args = parse_args()

    print("\n📚 Google Scholar BibTeX Crawler")
    print("─" * 50)

    input_file = args.input
    if not os.path.exists(input_file):
        print(f"❌ 错误: 文件 '{input_file}' 不存在")
        sys.exit(1)

    output_file = args.output or os.path.splitext(input_file)[0] + ".bib"

    print(f"📂 输入: {input_file}")
    print(f"📄 输出: {output_file}")
    if args.proxy:
        print(f"🔗 代理: {args.proxy}")
    print()

    # 读取输入
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]

    # 断点续传：只跳过已成功的条目，失败条目会重新尝试
    done = load_progress(output_file)
    todo = [q for q in lines if q not in done]
    if done:
        print(f"⏩ 断点续传: 跳过已成功的 {len(done)} 条，待处理 {len(todo)} 条\n")

    # 启动浏览器
    print("🌐 启动浏览器...")
    browser = None
    success = 0
    failed = []

    try:
        browser = create_browser(proxy=args.proxy)
        wait = WebDriverWait(browser, 15)

        browser.get("https://scholar.google.com")
        random_delay(2, 3)
        load_cookies(browser)
        browser.get("https://scholar.google.com")
        random_delay(2, 3)

        if check_captcha(browser):
            wait_for_captcha(browser)

        # 始终以 'w' 重写文件，先把已成功的缓存写回（不会丢数据，也清掉旧的 % Failed），
        # 再处理剩余条目并追加。
        with open(output_file, 'w', encoding='utf-8') as f:
            for query in lines:
                if query in done:
                    f.write(f"% Query: {query}\n{done[query]}\n\n")
            f.flush()

            for idx, query in enumerate(todo, 1):
                display = query[:50] + "..." if len(query) > 50 else query
                print(f"\n🔍 [{idx}/{len(todo)}] {display}")

                f.write(f"% Query: {query}\n")
                f.flush()

                bibtex = get_bibtex(browser, wait, query)

                if bibtex:
                    f.write(bibtex + "\n\n")
                    success += 1
                    print(f"   ✅ 成功")
                else:
                    f.write("% Failed\n\n")
                    failed.append(query[:50])
                    print(f"   ❌ 失败")
                f.flush()

                delay = random_delay()
                print(f"   ⏳ 等待 {delay:.1f}s")

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        logger.exception("详细错误信息")
    finally:
        if browser:
            save_cookies(browser)
            browser.quit()

    # 结果统计
    print(f"\n{'─' * 50}")
    print(f"🎉 完成!")
    print(f"   📊 成功: {success}  ❌ 失败: {len(failed)}")
    if success + len(failed) > 0:
        rate = success / (success + len(failed)) * 100
        bar_len = 20
        filled = int(bar_len * rate / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"   📈 成功率: [{bar}] {rate:.1f}%")
    print(f"   📄 输出: {output_file}")

    if failed:
        print(f"\n⚠️  失败条目:")
        for item in failed[:5]:
            print(f"   • {item}")
        if len(failed) > 5:
            print(f"   ... 共 {len(failed)} 条")


if __name__ == '__main__':
    main()
