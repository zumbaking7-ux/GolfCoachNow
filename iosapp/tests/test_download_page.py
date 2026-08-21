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


# --- The root, which is what somebody types ------------------------------


def test_the_root_serves_the_web_app(client, tmp_path, monkeypatch):
    """Somebody who types app.golfcoachnow.org expects the app, not a status
    blob. The root used to answer with health JSON, which was fine while the
    only address was a hosting subdomain nobody would type by hand."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "app.html").write_text(
        "<!doctype html><title>GolfCoachNow</title><div class='skill-card'>",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_STATIC_DIR", str(static))

    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "GolfCoachNow" in r.text


def test_health_still_answers_for_machines(client):
    """The deploy runbook checks this, and it is the first thing to look at
    when the site seems down: it answers only if the process actually
    started, which a broken import prevents."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "GolfCoachNow API"}


def test_an_unpublished_web_app_does_not_404_the_root(client, tmp_path, monkeypatch):
    """A host with no static files copied yet should say something true
    rather than look broken."""
    monkeypatch.setattr(server, "_STATIC_DIR", str(tmp_path / "nothing-here"))

    r = client.get("/")
    assert r.status_code == 200
    assert "running" in r.text.lower()


def test_index_html_is_accepted_when_app_html_is_absent(client, tmp_path, monkeypatch):
    """The deploy writes the page under both names. Either one will do."""
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Only index</title>", encoding="utf-8")
    monkeypatch.setattr(server, "_STATIC_DIR", str(static))

    assert "Only index" in client.get("/").text
