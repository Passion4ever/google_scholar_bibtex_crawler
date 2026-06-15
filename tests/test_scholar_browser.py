import os

from scholar_bibtex.scholar_browser import looks_blocked, find_isolated_chromium


def test_sorry_url_is_blocked():
    assert looks_blocked("https://scholar.google.com/sorry/index?continue=...", "")


def test_unusual_traffic_html_is_blocked():
    assert looks_blocked("https://scholar.google.com/scholar?q=x",
                         "<html>...our systems have detected unusual traffic...</html>")


def test_recaptcha_html_is_blocked():
    assert looks_blocked("https://scholar.google.com/scholar?q=x",
                         "<div class='g-recaptcha'></div>")


def test_normal_page_not_blocked():
    assert not looks_blocked("https://scholar.google.com/scholar?q=x",
                             "<div class='gs_r gs_or gs_scl'>results...</div>")


def test_find_isolated_chromium_none_when_absent(tmp_path):
    assert find_isolated_chromium(bases=[str(tmp_path)]) is None


def test_find_isolated_chromium_locates_linux_binary(tmp_path):
    exe = tmp_path / "chromium-1217" / "chrome-linux" / "chrome"
    exe.parent.mkdir(parents=True)
    exe.write_text("#!/bin/sh\n")
    found = find_isolated_chromium(bases=[str(tmp_path)])
    assert found == str(exe)


def test_find_isolated_chromium_picks_highest_version(tmp_path):
    for ver in ("chromium-1000", "chromium-1217", "chromium-1100"):
        exe = tmp_path / ver / "chrome-linux" / "chrome"
        exe.parent.mkdir(parents=True)
        exe.write_text("x")
    found = find_isolated_chromium(bases=[str(tmp_path)])
    assert "chromium-1217" in found
