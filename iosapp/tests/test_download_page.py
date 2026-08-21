"""The install page, served at a url worth sending to somebody.

The same file the static mapping already serves at /static/download.html. That
path reads like a file because it is one, and this is the link that gets
pasted to testers and to journalists, so it gets a real route.
"""

import io
import os

import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def published(tmp_path, monkeypatch):
    """Put a page where the route looks for one."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "download.html").write_text(
        "<!doctype html><title>Get Golf Coach Now</title>"
        '<a href="/static/download/golfcoachnow.apk">Install</a>',
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_STATIC_DIR", str(static))


def test_the_page_is_served(client, published):
    r = client.get("/download")
    assert r.status_code == 200
    assert "Get Golf Coach Now" in r.text


def test_it_is_html_not_json(client, published):
    """A link somebody opens in a browser, so it has to render rather than
    download or display as text."""
    assert client.get("/download").headers["content-type"].startswith("text/html")


def test_it_still_points_at_the_apk(client, published):
    assert "/static/download/golfcoachnow.apk" in client.get("/download").text


def test_it_is_read_per_request(client, published, tmp_path):
    """Replacing the file must take effect without a reload, which is how
    every other static asset on this host already behaves."""
    assert "Get Golf Coach Now" in client.get("/download").text

    (tmp_path / "static" / "download.html").write_text(
        "<!doctype html><title>Updated</title>", encoding="utf-8"
    )
    assert "Updated" in client.get("/download").text


def test_a_missing_page_is_a_clean_404(client, tmp_path, monkeypatch):
    """Rather than a 500. The page not being published yet is a state, not a
    fault, and it should not read like the server is broken."""
    monkeypatch.setattr(server, "_STATIC_DIR", str(tmp_path / "nothing-here"))
    assert client.get("/download").status_code == 404


def test_it_needs_no_account(client, published):
    """Whoever opens this has not signed in - they do not have the app yet."""
    assert client.get("/download").status_code == 200
