"""Validator: presence checks, hero heuristics, OBSERVE rendering."""

from __future__ import annotations

from scaler_cloner.agent.validator import validate_index_html


def test_full_page_passes():
    html = """\
<!doctype html><html><head><title>x</title><link rel="stylesheet" href="s.css"></head>
<body>
  <header><nav>logo</nav></header>
  <main><section class="hero"><h1>headline</h1></section></main>
  <footer>©</footer>
</body></html>"""
    v = validate_index_html(html)
    assert v.ok
    assert v.missing == []


def test_missing_header():
    html = '<section class="hero"><h1>x</h1></section><footer>x</footer>'
    v = validate_index_html(html)
    assert not v.ok
    assert "<header>" in v.missing


def test_missing_footer():
    html = '<header>x</header><section class="hero"><h1>x</h1></section>'
    v = validate_index_html(html)
    assert not v.ok
    assert "<footer>" in v.missing


def test_hero_via_section_with_heading():
    html = '<header>x</header><section><h2>Build a career</h2></section><footer>x</footer>'
    v = validate_index_html(html)
    assert v.ok


def test_hero_via_class_hint():
    html = '<header>x</header><div class="banner-large">marketing copy</div><footer>x</footer>'
    v = validate_index_html(html)
    assert v.ok  # "banner" matches a hero hint


def test_no_styles_is_a_note_not_a_failure():
    html = '<header>x</header><section><h1>x</h1></section><footer>x</footer>'
    v = validate_index_html(html)
    assert v.ok
    assert any("CSS" in n for n in v.notes)


def test_observe_message_lists_missing():
    html = '<section><h1>only hero</h1></section>'
    msg = validate_index_html(html).as_observe()
    assert "INCOMPLETE" in msg
    assert "<header>" in msg and "<footer>" in msg
