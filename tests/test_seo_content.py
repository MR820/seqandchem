from pathlib import Path

import app as app_module
from app import BIO_PAGES, PAGE_META
from presets import PRESETS
from seo_copy import PRESET_EXTRAS

ROOT = Path(__file__).resolve().parents[1]


def test_unindexed_presets_have_long_copy():
    assert set(PRESET_EXTRAS) <= set(PRESETS)
    for slug, extra in PRESET_EXTRAS.items():
        assert "Frequently asked questions" in extra
        assert len(PRESETS[slug]["prose"]) >= 1900


def test_priority_pages_have_substantive_copy():
    assert len(PRESETS["pdb-to-smiles"]["prose"]) >= 3500
    for term in ("RDKit", "OpenBabel", "Frequently asked questions", "FAQPage"):
        assert term in PRESETS["pdb-to-smiles"]["prose"]

    formula = (ROOT / "templates" / "formula.html").read_text(encoding="utf-8")
    assert "Molecular Weight Calculator" in formula
    assert "monoisotopic" in formula
    assert "FAQPage" in formula
    assert PAGE_META["formula"]["title"].startswith("Molecular Weight Calculator")

    revcomp = (ROOT / "templates" / "bio_reverse_complement.html").read_text(encoding="utf-8")
    assert BIO_PAGES["bio-reverse-complement"]["h1"] == "Reverse Complement Calculator"
    assert "IUPAC" in revcomp
    assert "Biopython" in revcomp
    assert "FAQPage" in revcomp

    privacy = (ROOT / "templates" / "privacy.html").read_text(encoding="utf-8")
    privacy_flat = " ".join(privacy.split())
    assert "Cloudflare Web Analytics" in privacy_flat
    assert "cookie-free" in privacy_flat
    assert "goatcounter" not in privacy.lower()

    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "goatcounter" not in base.lower()
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "goatcounter" not in app_js.lower()


def test_second_batch_pages_have_substantive_copy():
    checks = {
        "three_d.html": ("Frequently asked questions", "FAQPage", "force field"),
        "similarity.html": ("Frequently asked questions", "FAQPage", "Worked example"),
        "lipinski.html": ("Frequently asked questions", "FAQPage", "aspirin"),
        "bio_gc_content.html": ("GC content formula", "FAQPage", "primer"),
    }
    for name, terms in checks.items():
        html = (ROOT / "templates" / name).read_text(encoding="utf-8")
        for term in terms:
            assert term in html, f"{name} missing {term}"

    assert PAGE_META["3d"]["description"].startswith("Generate an interactive 3D")
    assert PAGE_META["similarity"]["title"].startswith("Tanimoto Similarity Calculator")
    assert PAGE_META["lipinski"]["title"].startswith("Lipinski Rule of Five Calculator")
    assert BIO_PAGES["bio-gc-content"]["title"].startswith("GC Content Calculator")


def test_third_batch_pages_have_substantive_copy():
    checks = {
        "properties.html": ("Descriptors provided", "FAQPage", "aspirin"),
        "bio_translate.html": ("Amino acid decoder", "FAQPage", "How to read a codon chart"),
    }
    for name, terms in checks.items():
        html = (ROOT / "templates" / name).read_text(encoding="utf-8")
        for term in terms:
            assert term in html, f"{name} missing {term}"

    assert PAGE_META["properties"]["title"].startswith("Molecular Property Calculator")
    assert BIO_PAGES["bio-translate"]["title"].startswith("DNA to Protein Translation")

    iupac = (ROOT / "templates" / "iupac.html").read_text(encoding="utf-8")
    for term in ("IUPAC Name to Structure Generator", "Example names", "FAQPage"):
        assert term in iupac
    assert PAGE_META["iupac"]["title"].startswith("IUPAC Name Generator")

    converter_checks = {
        "mol_to_smiles.html": ("What can go wrong", "FAQPage", "V3000"),
        "smiles_to_png.html": ("PNG or SVG", "FAQPage", "300 × 300"),
        "sdf_to_smiles.html": ("What is preserved and what is lost", "FAQPage", "$$$$"),
    }
    for name, terms in converter_checks.items():
        html = (ROOT / "templates" / name).read_text(encoding="utf-8")
        for term in terms:
            assert term in html, f"{name} missing {term}"
    assert PRESETS["smiles-to-mol"]["title"].startswith("SMILES to MOL Converter")
    assert "V2000" in PRESETS["smiles-to-mol"]["prose"]
    assert "FAQPage" in PRESETS["smiles-to-mol"]["prose"]
    assert PAGE_META["mol-to-smiles"]["title"].startswith("MOL to SMILES Converter")
    assert PAGE_META["smiles-to-png"]["title"].startswith("SMILES to PNG")



def test_new_tool_pages_have_content():
    checks = {
        "bio_protein_mw.html": ("Frequently asked questions", "FAQPage", "monoisotopic"),
        "bio_dna_mw.html": ("Frequently asked questions", "FAQPage", "dsDNA"),
        "codon_chart.html": ("Codon chart", "FAQPage", "TGA"),
        "bio_primer_tm.html": ("Frequently asked questions", "FAQPage", "salt-adjusted"),
    }
    for name, terms in checks.items():
        html = (ROOT / "templates" / name).read_text(encoding="utf-8")
        for term in terms:
            assert term in html, f"{name} missing {term}"

    pdbqt = PRESETS["smiles-to-pdbqt"]["prose"]
    assert "AutoDock" in pdbqt
    assert "FAQPage" in pdbqt
    assert BIO_PAGES["bio-protein-mw"]["title"].startswith("Protein Molecular Weight Calculator")
    assert BIO_PAGES["bio-dna-mw"]["title"].startswith("DNA Molecular Weight Calculator")
    assert BIO_PAGES["bio-primer-tm"]["title"].startswith("Primer Tm Calculator")
    assert PAGE_META["codon-chart"]["title"].startswith("Codon Chart")


def test_expanded_converter_presets():
    for slug in ("sdf-to-mol", "inchi-to-mol", "sdf-to-pdb",
                 "sdf-to-inchi", "pdb-to-inchi", "mol-to-sdf", "inchi-to-inchikey",
                 "pdb-to-sdf", "smiles-to-cml"):
        prose = PRESETS[slug]["prose"]
        assert len(prose) >= 3000
        assert "FAQPage" in prose
        assert "Frequently asked questions" in prose


def test_pdbqt_guide():
    from guides import GUIDES
    g = GUIDES["smiles-to-pdbqt-autodock-vina"]
    assert "AutoDock Vina" in g["title"]
    assert "FAQPage" in g["prose"]
    assert len(g["prose"]) >= 5000


def test_about_page():
    about = (ROOT / "templates" / "about.html").read_text(encoding="utf-8")
    for term in ("About SeqChem", "AboutPage", "Cloudflare Web Analytics",
                 "Cite SeqChem", "10.5281/zenodo.24310592", "bio.tools/seqchem",
                 "github.com/MR820/seqandchem/issues", 'id="how-the-tools-work"',
                 'id="cite-seqchem"'):
        assert term in about
    assert PAGE_META["about"]["title"].startswith("About SeqChem")

    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    for term in ("https://bio.tools/seqchem", "https://doi.org/10.5281/zenodo.24310592",
                 "Methodology", "Cite"):
        assert term in base


def test_structured_data_is_valid_json():
    import json
    import re

    client = app_module.app.test_client()
    for path in ("/", "/about", "/properties", "/3d"):
        html = client.get(path).data.decode()
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
        assert blocks, f"{path} has no JSON-LD"
        for block in blocks:
            json.loads(block)


def test_molecular_weight_guide():
    from guides import GUIDES
    g = GUIDES["molecular-weight-average-vs-monoisotopic"]
    assert "Monoisotopic" in g["title"]
    assert "FAQPage" in g["prose"]
    assert len(g["prose"]) >= 5000


def test_under_500_pages_expanded():
    page_checks = {
        "depict.html": ("2D structure generator", "FAQPage"),
        "substructure.html": ("SMARTS syntax essentials", "FAQPage"),
        "convert.html": ("Format families", "FAQPage"),
        "batch.html": ("What is preserved", "FAQPage"),
        "bio_fasta_to_fastq.html": ("placeholder quality scores", "FAQPage"),
        "bio_fastq_to_fasta.html": ("What is preserved and what is lost", "FAQPage"),
        "smiles_to_inchi.html": ("Worked example", "FAQPage"),
        "inchi_to_smiles.html": ("Worked example", "FAQPage"),
        "smiles_to_sdf.html": ("2D vs 3D", "FAQPage"),
    }
    for name, terms in page_checks.items():
        html = (ROOT / "templates" / name).read_text(encoding="utf-8")
        for term in terms:
            assert term in html, f"{name} missing {term}"

    for slug in ("mol-to-inchi", "mol2-to-sdf", "smiles-to-inchikey", "xyz-to-sdf"):
        prose = PRESETS[slug]["prose"]
        assert len(prose) >= 3000
        assert "FAQPage" in prose


def test_error_pages_skip_cloudflare_analytics(monkeypatch):
    monkeypatch.setattr(app_module, "CF_BEACON_TOKEN", "test-token")
    client = app_module.app.test_client()
    assert "cloudflareinsights" in client.get("/").data.decode()
    for path in ("/no-such-page", "/panel/"):
        body = client.get(path).data.decode()
        assert "cloudflareinsights" not in body
