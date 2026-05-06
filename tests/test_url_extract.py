"""URL extraction from free-form user requests."""

from __future__ import annotations

from scaler_cloner.agent.url import extract_target


def test_explicit_https_url():
    assert extract_target("clone https://stripe.com please") == ("https://stripe.com", "stripe.com")


def test_url_with_path_and_trailing_punct():
    url, host = extract_target("see https://example.com/foo/bar.")
    assert url == "https://example.com/foo/bar"
    assert host == "example.com"


def test_bare_host():
    assert extract_target("clone scaler.com") == ("https://scaler.com", "scaler.com")


def test_subdomain():
    assert extract_target("hit blog.acme.io") == ("https://blog.acme.io", "blog.acme.io")


def test_no_url_returns_none():
    assert extract_target("just clone it") == (None, None)


def test_empty():
    assert extract_target("") == (None, None)


def test_first_url_wins():
    url, _ = extract_target("compare https://a.com and https://b.com")
    assert url == "https://a.com"
