"""
Google Scholar BibTeX Crawler

自动从 Google Scholar 搜索论文并提取 BibTeX 引用信息。

安装依赖:
    pip install undetected-chromedriver selenium

使用方法:
    python get_google_scholar_bibtex.py <input.txt> [output.bib]
"""

import os
import sys
import time
import random
import pickle

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
COOKIE_FILE = ".google_scholar_cookies.pkl"
MIN_DELAY = 5
MAX_DELAY = 10


def random_delay(min_sec=MIN_DELAY, max_sec=MAX_DELAY):
    """随机延迟"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def create_browser():
    """创建浏览器"""
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')
    return uc.Chrome(options=options)


def save_cookies(browser):
    """保存 Cookies"""
    try:
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(browser.get_cookies(), f)
    except:
        pass


def load_cookies(browser):
    """加载 Cookies"""
    if not os.path.exists(COOKIE_FILE):
        return
    try:
        with open(COOKIE_FILE, 'rb') as f:
            for cookie in pickle.load(f):
                try:
                    browser.add_cookie(cookie)
                except:
                    pass
    except:
        pass


def check_captcha(browser):
    """检测验证码"""
    try:
        page = browser.page_source.lower()
        indicators = ["captcha", "unusual traffic", "not a robot", "sorry"]
        return any(x in page for x in indicators) or "sorry" in browser.current_url.lower()
    except:
        return False


def wait_for_captcha(browser):
    """等待用户解决验证码"""
    print("\n" + "=" * 50)
    print("检测到验证码！请在浏览器中完成验证")
    print("完成后按 Enter 继续...")
    print("=" * 50)
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
    search_url = f"https://scholar.google.com/scholar?q={search_query.replace(' ', '+')}"

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

        # 点击引用按钮
        try:
            cite_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".gs_or_cit.gs_or_btn.gs_nph")))
            cite_btn.click()
            random_delay(1, 2)
        except TimeoutException:
            return None

        # 点击 BibTeX 链接
        try:
            bibtex_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "BibTeX")))
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
        except:
            pass

        # 备用：从 body 获取
        try:
            text = browser.find_element(By.TAG_NAME, "body").text.strip()
            if '@' in text and len(text) < 2000:
                return text
        except:
            pass

        return None

    except Exception as e:
        print(f"  异常: {e}")
        return None


def load_progress(output_file):
    """加载已处理记录"""
    processed = set()
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('% Query:'):
                        processed.add(line.replace('% Query:', '').strip())
        except:
            pass
    return processed


def main():
    print("Google Scholar BibTeX Crawler")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("用法: python get_google_scholar_bibtex.py <input.txt> [output.bib]")
        print("\n示例:")
        print("  python get_google_scholar_bibtex.py papers.txt")
        print("  python get_google_scholar_bibtex.py papers.txt refs.bib")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"错误: 文件 '{input_file}' 不存在")
        sys.exit(1)

    output_file = sys.argv[2] if len(sys.argv) >= 3 else os.path.splitext(input_file)[0] + ".bib"

    print(f"输入: {input_file}")
    print(f"输出: {output_file}\n")

    # 读取输入
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]

    # 断点续传
    processed = load_progress(output_file)
    if processed:
        print(f"断点续传: 跳过已处理的 {len(processed)} 条\n")

    # 启动浏览器
    print("启动浏览器...")
    browser = create_browser()
    wait = WebDriverWait(browser, 15)

    browser.get("https://scholar.google.com")
    random_delay(2, 3)
    load_cookies(browser)
    browser.get("https://scholar.google.com")
    random_delay(2, 3)

    if check_captcha(browser):
        wait_for_captcha(browser)

    success = 0
    failed = []
    mode = 'a' if processed else 'w'

    try:
        with open(output_file, mode, encoding='utf-8') as f:
            for idx, query in enumerate(lines, 1):
                if query in processed:
                    continue

                display = query[:50] + "..." if len(query) > 50 else query
                print(f"[{idx}/{len(lines)}] {display}")

                f.write(f"% Query: {query}\n")
                f.flush()

                bibtex = get_bibtex(browser, wait, query)

                if bibtex:
                    f.write(bibtex + "\n\n")
                    success += 1
                    print(f"  成功")
                else:
                    f.write("% Failed\n\n")
                    failed.append(query[:50])
                    print(f"  失败")
                f.flush()

                delay = random_delay()
                print(f"  等待 {delay:.1f}s")

    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        save_cookies(browser)
        browser.quit()

    # 结果统计
    print(f"\n{'=' * 50}")
    print(f"完成! 成功: {success}, 失败: {len(failed)}")
    if success + len(failed) > 0:
        print(f"成功率: {success / (success + len(failed)) * 100:.1f}%")
    print(f"输出: {output_file}")

    if failed:
        print(f"\n失败条目:")
        for item in failed[:5]:
            print(f"  - {item}")
        if len(failed) > 5:
            print(f"  ... 等 {len(failed)} 条")


if __name__ == '__main__':
    main()
