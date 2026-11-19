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


def _bio(op, data, **extra):
    body = {"op": op, "data": data}
    body.update(extra)
    return client().post("/api/v1/bio", json=body)


def test_fastq_length_mismatch_is_400_and_not_a_success():
    response = _bio("fastq2fasta", "@read1\nATGC\n+\nII\n")
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "Invalid FASTQ: sequence and quality lengths differ"
    assert body["detail"] == (
        "Record 1 (read1): sequence length 4, quality length 2"
    )
    assert "result" not in body

    same = client().post("/api/bio", json={
        "op": "fastq2fasta", "data": "@read1\nATGC\n+\nII\n",
    })
    assert same.status_code == 400
    assert same.get_json()["ok"] is False


def test_fastq_valid_multi_record_and_middle_failure():
    good = "@read1\nATGC\n+\nIIII\n@read2\nTTAA\n+\nIIII\n"
    response = _bio("fastq2fasta", good)
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert body["result"] == ">read1\nATGC\n>read2\nTTAA"

    bad = "@ok\nATGC\n+\nIIII\n@bad\nATGC\n+\nII\n@later\nGG\n+\nII\n"
    response = _bio("fastq2fasta", bad)
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert "result" not in body
    assert "Record 2 (bad)" in body["detail"]


def test_revcomp_rejects_digits_and_keeps_iupac_rna_and_records():
    bad = _bio("revcomp", "12345")
    assert bad.status_code == 400
    body = bad.get_json()
    assert body["ok"] is False
    assert body["error"] == (
        "Invalid sequence: characters are not DNA, RNA or IUPAC ambiguity codes"
    )
    assert "result" not in body
    assert "'1'" in body["detail"]

    iupac = _bio("revcomp", "ATGCRY")
    assert iupac.status_code == 200
    assert iupac.get_json() == {"ok": True, "result": "RYGCAT"}

    rna = _bio("revcomp", "AUGC")
    assert rna.status_code == 200
    assert rna.get_json()["result"] == "GCAT"

    records = _bio("revcomp", ">a\nATGC\nRY\n>b\nAU\n")
    assert records.status_code == 200
    assert records.get_json()["result"] == ">a\nRYGCAT\n>b\nAT"

    lines = _bio("revcomp", "ATGC\nRY")
    assert lines.status_code == 200
    assert lines.get_json()["result"] == "RYGCAT"


def test_bio_empty_and_unknown_op_stay_client_errors():
    empty = _bio("stats", "")
    assert empty.status_code == 400
    assert empty.get_json()["ok"] is False
    unknown = _bio("nope", "ATGC")
    assert unknown.status_code == 400
    assert unknown.get_json()["error"] == "Unknown operation"


def test_formula_mode_shape_matches_the_docs():
    response = client().post("/api/v1/formula", json={
        "mode": "formula", "formula": "C9H8O4",
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["formula"] == "C9H8O4"
    assert body["mw"] == 180.159
    assert body["atoms"] == 21
    assert [row["element"] for row in body["composition"]] == ["C", "O", "H"]
    assert body["composition"][0]["count"] == 9


def test_docs_describe_the_implemented_behavior():
    api = client().get("/api")
    assert api.status_code == 200
    page = api.get_data(as_text=True)
    assert '"atoms": "13"' in page
    assert "heavy-atom count" in page
    assert "not 21" in page
    assert '"rows"' in page
    assert "not a map of" in page
    assert "Invalid SMARTS pattern" in page
    assert "six-frame" not in page

    bio = client().get("/bio/")
    assert bio.status_code == 200
    text = bio.get_data(as_text=True)
    assert "six-frame" not in text
    assert "three forward reading frames" in text

    fastq = client().get("/bio/fastq-to-fasta")
    assert fastq.status_code == 200
    assert b"ASCII 33-126" in fastq.data

    rev = client().get("/bio/reverse-complement")
    assert rev.status_code == 200
    assert b"complemented to A" in rev.data

    sub = client().get("/substructure")
    assert sub.status_code == 200
    assert b"not a search with zero hits" in sub.data

    guide = client().get("/guides/fasta-vs-fastq")
    assert guide.status_code == 200
    assert b"does not drop the quality string" in guide.data

    embed = client().get("/embed")
    widget = client().get("/embed/convert?from=smi&to=inchi")
    assert embed.status_code == 200
    assert embed.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert widget.status_code == 200
    assert b'id="w-in"' in widget.data
    assert widget.headers.get("Content-Security-Policy") == "frame-ancestors https: http: 'self'"

    spec = client().get("/api/openapi.json").get_json()
    assert "heavy-atom" in spec["paths"]["/api/v1/properties"]["post"]["description"]
    assert "422" in spec["paths"]["/api/v1/substructure"]["post"]["description"]
    formula = spec["paths"]["/api/v1/formula"]["post"]["description"]
    assert "rows" in formula and "composition" in formula
    bio_desc = spec["paths"]["/api/v1/bio"]["post"]["description"]
    assert "0, 1 or 2" in bio_desc
    assert "six" not in bio_desc.lower()
