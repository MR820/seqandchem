import re

import app as app_module


def client():
    return app_module.app.test_client()


def test_privacy_page():
    response = client().get("/privacy")
    assert response.status_code == 200
    assert b"Privacy Policy" in response.data
    assert b"noindex" not in response.data


def test_custom_404_and_noindex():
    response = client().get("/does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data
    assert b'content="noindex,nofollow"' in response.data


def test_api_404_is_json():
    response = client().get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["ok"] is False


def test_favicon_redirect():
    response = client().get("/favicon.ico")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/favicon.svg")


def test_page_title_is_the_only_h1():
    response = client().get("/convert")
    assert response.status_code == 200
    body = response.data.decode()
    assert len(re.findall(r"<h1\b", body, re.I)) == 1
    assert "Chemical File Format Converter" in body
    assert '<h1><a href="/">SeqChem</a></h1>' not in body


def test_sitemap_includes_privacy_and_new_lastmod():
    response = client().get("/sitemap.xml")
    assert response.status_code == 200
    assert b"/privacy" in response.data
    assert b"<lastmod>2026-11-16</lastmod>" in response.data


def test_formats_dir_filter(monkeypatch):
    fake = {
        "smi": {"desc": "SMILES", "read": True, "write": True},
        "png": {"desc": "PNG", "read": False, "write": True},
    }
    monkeypatch.setattr(app_module, "supported_formats", lambda: fake)
    response = client().get("/api/formats?dir=read")
    data = response.get_json()
    assert data["dir"] == "read"
    assert [item["id"] for item in data["items"]] == ["smi"]


def test_iupac_cache(monkeypatch):
    calls = []
    app_module._IUPAC_CACHE.clear()

    def fake(name):
        calls.append(name)
        return {"ok": True, "resolved": True, "source": "test", "smiles": "CCO"}

    monkeypatch.setattr(app_module, "_resolve_iupac", fake)
    first = app_module._cached_iupac_lookup("ethanol")
    second = app_module._cached_iupac_lookup("ethanol")
    assert first == second
    assert calls == ["ethanol"]


def test_feedback_body_limit():
    response = client().post(
        "/api/feedback",
        data='{"message":"' + "x" * 20000 + '"}',
        content_type="application/json",
    )
    assert response.status_code == 413
    assert response.get_json()["ok"] is False
