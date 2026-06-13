from scholar_bibtex.scholar_browser import looks_blocked


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
