"""Google Scholar 兜底抓取。仅在 API 全未命中时调用。

懒导入 selenium/undetected-chromedriver,使核心无需这些依赖。
实际抓取逻辑复用项目根目录的 get_google_scholar_bibtex.py。
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _make_browser(proxy: Optional[str]):
    import get_google_scholar_bibtex as legacy  # 懒导入
    return legacy.create_browser(proxy=proxy)


def _scrape(browser, query: str) -> Optional[str]:
    import get_google_scholar_bibtex as legacy
    from selenium.webdriver.support.ui import WebDriverWait
    wait = WebDriverWait(browser, 15)
    if legacy.check_captcha(browser):
        legacy.wait_for_captcha(browser)
    return legacy.get_bibtex(browser, wait, query)


def _quit_browser(browser) -> None:
    try:
        browser.quit()
    except Exception as e:
        logger.debug("关闭浏览器失败: %s", e)


def fetch(query: str, proxy: Optional[str] = None) -> Optional[str]:
    """同步:启动浏览器抓一条;任何异常都降级为 None。"""
    browser = None
    try:
        browser = _make_browser(proxy)
        return _scrape(browser, query)
    except Exception as e:
        logger.warning("Scholar 兜底失败: %s", e)
        return None
    finally:
        if browser is not None:
            _quit_browser(browser)
