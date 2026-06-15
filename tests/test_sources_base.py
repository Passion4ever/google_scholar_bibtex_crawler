from scholar_bibtex.sources.base import USER_AGENT, classify_http_error
from scholar_bibtex.ratelimit import TransientError
import pytest


def test_user_agent_includes_mailto_when_given():
    ua = USER_AGENT(mailto="me@example.com")
    assert "me@example.com" in ua


def test_user_agent_without_mailto():
    ua = USER_AGENT(mailto=None)
    assert "scholar_bibtex" in ua


def test_classify_http_error_429_is_transient():
    with pytest.raises(TransientError):
        classify_http_error(429)


def test_classify_http_error_503_is_transient():
    with pytest.raises(TransientError):
        classify_http_error(503)


def test_classify_http_error_404_not_transient():
    # 404 等客户端错误不抛 TransientError(返回 None 让调用方处理)
    assert classify_http_error(404) is None
