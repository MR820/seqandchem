"""OpenBabel CLI integration tests.

These call the real ``obabel`` binary (production uses 3.1.1). They are not mocks:
a missing CLI fails the test. CI installs the distro ``openbabel`` package.
"""
import shutil
import subprocess

import pytest

import app as app_module


def client():
    return app_module.app.test_client()


@pytest.fixture(scope="module", autouse=True)
def require_obabel():
    if shutil.which("obabel") is None:
        pytest.fail(
            "OpenBabel CLI (obabel) is required; CI installs the openbabel package"
        )
    proc = subprocess.run(["obabel", "-V"], capture_output=True, text=True)
    banner = (proc.stdout or "") + (proc.stderr or "")
    assert "Open Babel" in banner


def test_invalid_smarts_is_422_and_a_real_miss_is_empty():
    bad = client().post("/api/v1/substructure", json={
        "data": "CCO", "from": "smi", "smarts": "[[[",
    })
    assert bad.status_code == 422
    body = bad.get_json()
    assert body["ok"] is False
    assert body["error"] == "Invalid SMARTS pattern"
    assert "SMARTS Error" in body["detail"]
    assert "matches" not in body
    assert "count" not in body

    miss = client().post("/api/v1/substructure", json={
        "data": "CCO", "from": "smi", "smarts": "c1ccccc1",
    })
    assert miss.status_code == 200
    body = miss.get_json()
    assert body["ok"] is True
    assert body["count"] == 0
    assert body["matches"] == []
    assert "SMARTS Error" not in body.get("log", "")

    hit = client().post("/api/v1/substructure", json={
        "data": "CCO\nc1ccccc1\nCCC", "from": "smi", "smarts": "c1ccccc1",
    })
    assert hit.status_code == 200
    body = hit.get_json()
    assert body["ok"] is True
    assert body["matches"] == ["c1ccccc1"]
    assert body["count"] == 1

    # A molecule OpenBabel cannot read is not reported as a bad SMARTS pattern.
    broken = client().post("/api/v1/substructure", json={
        "data": "bad", "from": "smi", "smarts": "C",
    })
    assert broken.status_code == 200
    body = broken.get_json()
    assert body["ok"] is True
    assert body["count"] == 0
    assert "error" not in body


def test_ethanol_property_mw_matches_the_docs():
    response = client().post("/api/v1/properties", json={"data": "CCO", "from": "smi"})
    assert response.status_code == 200
    assert response.get_json()["rows"][0]["props"]["MW"] == "46.0684"


def test_properties_atoms_are_heavy_atoms_for_aspirin():
    response = client().post("/api/v1/properties", json={
        "data": "CC(=O)Oc1ccccc1C(=O)O", "from": "smi",
    })
    assert response.status_code == 200
    props = response.get_json()["rows"][0]["props"]
    assert props["formula"] == "C9H8O4"
    assert props["atoms"] == "13"
    assert props["bonds"] == "13"
    assert props["MW"] == "180.157"
    assert props["MR"] == "44.9003"
    assert props["logP"] == "1.3101"
    assert props["TPSA"] == "63.6"
    assert props["rotors"] == "3"


def test_formula_structure_mode_returns_rows_not_top_level_fields():
    response = client().post("/api/v1/formula", json={
        "mode": "structure", "data": "CCO", "from": "smi",
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["rows"] == [{"smiles": "CCO", "formula": "C2H6O", "mw": 46.068}]
    assert "composition" not in body
    assert "formula" not in body
    assert "mw" not in body
    assert "atoms" not in body
