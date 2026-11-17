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


def test_batch_page_has_3d_preview():
    response = client().get("/batch")
    assert response.status_code == 200
    body = response.data.decode()
    assert 'id="batch-3d-wrap"' in body
    assert 'id="batch-3d"' in body
    assert 'value="--gen3d"' in body


def test_batch_preview_sdf_uses_gen3d(monkeypatch):
    seen = {}

    def fake_obabel(args, data=b"", timeout=None):
        seen["args"] = args
        seen["data"] = data
        return 0, b"SDF\n$$$$\n", "1 molecule converted"

    monkeypatch.setattr(app_module, "run_obabel", fake_obabel)
    out = app_module._batch_preview_sdf("smi", "sdf", "CCO\nCCC", ["--gen3d"])
    assert out == "SDF\n$$$$\n"
    assert "--gen3d" in seen["args"]
    assert seen["data"] == b"CCO\nCCC"


def test_batch_3d_limit(monkeypatch):
    fake = {
        "smi": {"desc": "SMILES", "read": True, "write": True},
        "sdf": {"desc": "SDF", "read": True, "write": True},
    }
    monkeypatch.setattr(app_module, "supported_formats", lambda: fake)
    data = "\n".join(["CCO"] * (app_module.MAX_BATCH_3D + 1))
    response = client().post("/api/batch", json={
        "data": data, "from": "smi", "to": "sdf", "opts": ["--gen3d"],
    })
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert "3D generation limit" in body["error"]


def test_batch_auto_gen3d_and_preview(monkeypatch):
    fake = {
        "smi": {"desc": "SMILES", "read": True, "write": True},
        "sdf": {"desc": "SDF", "read": True, "write": True},
    }
    monkeypatch.setattr(app_module, "supported_formats", lambda: fake)
    calls = []

    def fake_obabel(args, data=b"", timeout=None):
        calls.append((args, data))
        return 0, b"SDF\n$$$$\n", "1 molecule converted"

    monkeypatch.setattr(app_module, "run_obabel", fake_obabel)
    monkeypatch.setattr(app_module, "_heavy_acquire", lambda timeout: object())
    monkeypatch.setattr(app_module, "_heavy_release", lambda slot: None)

    response = client().post("/api/batch", json={
        "data": "CCO", "from": "smi", "to": "sdf",
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["preview_sdf"] == "SDF\n$$$$\n"
    assert calls and all("--gen3d" in args for args, _ in calls)
