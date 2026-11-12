"""
SeqChem — 化学与序列工具站
OpenBabel 负责分子处理，OPSIN/PubChem 负责名称解析，序列工具为纯 Python 实现
"""
import base64
import collections
import datetime
import gzip
import io
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from functools import lru_cache

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory
from flask_compress import Compress

from bio import (fasta_to_fastq, fastq_to_fasta, parse_fasta, parse_fastq,
                 reverse_complement, sequence_stats, translate)
from formula import (FormulaError, composition, hill_notation, molecular_weight,
                     parse_formula)
from guides import GUIDE_INDEX, GUIDES
from presets import PRESETS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OBABEL = "obabel"
TIMEOUT = 60
MAX_INPUT = 8 * 1024 * 1024  # 8MB for single-molecule endpoints
MAX_BATCH_INPUT = 64 * 1024 * 1024  # 64MB for /api/batch
MAX_BATCH_RECORDS = 5000           # records per batch run (any output format)
MAX_BATCH_IMAGES = 500             # records per run when the output is an image

app = Flask(__name__, static_folder=None)
Compress(app)
# 静态资源缓存 1 天；模板里带 ?v=<mtime> 版本号，改文件即失效
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400

def _asset_v(name):
    try:
        return int(os.path.getmtime(os.path.join(BASE_DIR, "static", name)))
    except OSError:
        return 0


@app.context_processor
def _inject_assets():
    return {
        "v_css": _asset_v("style.css"),
        "v_js": _asset_v("app.js"),
        "v_3dmol": _asset_v("3dmol-min.js"),
    }

THREE_D_FORMATS = {
    "sdf", "sd", "mol", "mdl", "mol2", "pdb", "xyz", "cml", "cif",
    "stl", "obj", "ply", "vrml", "wrl", "gpr",
}
TWO_D_SOURCES = {"smi", "can", "inchi", "inchikey", "txt", "smi"}

EXAMPLE_SMILES = "CC(=O)Oc1ccccc1C(=O)O"

# 高负载任务（3D 生成 / 批量）的并发闸门：每进程 1 个，2 个 worker = 全局最多 2 个
HEAVY_SLOTS = threading.BoundedSemaphore(1)
HEAVY_WAIT_SECONDS = 30


def heavy_busy():
    return jsonify({"ok": False, "error": "Server is busy with other heavy jobs, please retry in a moment"}), 429


# ────────────────────────────────────────────── 公开 API：CORS + 限流
# 真实客户端 IP 在 nginx stream(SNI) 层丢失，但若以后接入 Cloudflare 或
# PROXY protocol，这里会自动按真实 IP 分桶；否则退化为全局共享配额。
RATE_PER_CLIENT = 120          # 单客户端每分钟
RATE_GLOBAL = 300              # 全站每分钟
_RATE_LOCK = threading.Lock()
_RATE_HITS = collections.defaultdict(collections.deque)
_RATE_GLOBAL_HITS = collections.deque()


def _client_key():
    for hdr in ("CF-Connecting-IP", "X-Real-IP"):
        v = (request.headers.get(hdr) or "").strip()
        if v and v not in ("127.0.0.1", "::1"):
            return v
    for part in (request.headers.get("X-Forwarded-For") or "").split(","):
        part = part.strip()
        if part and part not in ("127.0.0.1", "::1"):
            return part
    return "shared"


def _rate_limited(bucket, limit, now, window):
    while bucket and bucket[0] < window:
        bucket.popleft()
    if len(bucket) >= limit:
        return max(1, int(60 - (now - bucket[0])))
    bucket.append(now)
    return 0


@app.before_request
def _api_rate_limit():
    if not request.path.startswith("/api/") or request.method == "OPTIONS":
        return None
    now = time.monotonic()
    window = now - 60
    with _RATE_LOCK:
        retry = _rate_limited(_RATE_GLOBAL_HITS, RATE_GLOBAL, now, window)
        if not retry:
            retry = _rate_limited(_RATE_HITS[_client_key()], RATE_PER_CLIENT, now, window)
        if len(_RATE_HITS) > 5000:  # 丢弃已空的桶，避免内存膨胀
            for k in [k for k, v in _RATE_HITS.items() if not v]:
                del _RATE_HITS[k]
    if retry:
        resp = jsonify({"ok": False, "error": "Rate limit exceeded",
                        "detail": f"Try again in {retry}s. Fair use: "
                                  f"{RATE_PER_CLIENT}/min per client, {RATE_GLOBAL}/min total."})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry)
        return resp
    return None


@app.after_request
def _frame_headers(resp):
    if request.path.startswith("/embed/"):
        resp.headers.setdefault("Content-Security-Policy", "frame-ancestors https: http: 'self'")
    elif not request.path.startswith("/api/"):
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return resp


@app.after_request
def _api_cors(resp):
    if request.path.startswith("/api/") or request.path == "/health":
        resp.headers.setdefault("Access-Control-Allow-Origin", "*")
        resp.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
        resp.headers.setdefault("Access-Control-Max-Age", "86400")
    return resp


MIME_BY_FORMAT = {
    "png": "image/png",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "stl": "model/stl",
    "ply": "application/octet-stream",
    "pdf": "application/pdf",
}


# ────────────────────────────────────────────── 工具函数
@lru_cache(maxsize=1)
def supported_formats():
    """Supported formats with read/write capability"""
    try:
        out = subprocess.run(
            [OBABEL, "-L", "formats"], capture_output=True, text=True, timeout=30
        ).stdout
    except Exception:
        return {}

    formats = {}
    for line in out.splitlines():
        m = re.match(r"^\s*([A-Za-z0-9]+)\s+--\s+(.*)$", line)
        if not m:
            continue
        fid, desc = m.group(1), m.group(2).strip()
        can_read = "[Write-only]" not in desc
        can_write = "[Read-only]" not in desc
        desc = re.sub(r"\s*\[(Read-only|Write-only)\]\s*$", "", desc).strip()
        formats[fid] = {"desc": desc, "read": can_read, "write": can_write}
    return formats


def valid_format(fmt):
    if not fmt or not re.fullmatch(r"[A-Za-z0-9]+", fmt):
        return False
    return fmt in supported_formats()


def run_obabel(args, data=b"", timeout=TIMEOUT):
    """Run obabel"""
    try:
        proc = subprocess.run(
            [OBABEL] + args,
            input=data,
            capture_output=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, b"", "Timed out after %d seconds, please reduce input size" % timeout
    except Exception as exc:  # noqa: BLE001
        return 1, b"", "Execution failed: %s" % exc


def payload(max_bytes=MAX_INPUT):
    data = request.get_json(silent=True) or {}
    text = data.get("data", "")
    if not isinstance(text, str):
        text = ""
    size = len(text.encode("utf-8", "ignore"))
    if size > max_bytes:
        raise ValueError(f"Input too large: {size / 1048576:.1f} MB "
                         f"(limit {max_bytes // 1048576} MB)")
    return data, text


def err(message, code=400, detail=""):
    return jsonify({"ok": False, "error": message, "detail": detail}), code


def _obabel_error(frm, errtext):
    """Turn an OpenBabel stderr dump into something a user can act on."""
    raw = errtext.strip()[:2000] or "No output"
    low = raw.lower()
    if "cannot read" in low or "error in reading file" in low or "parse error" in low:
        return err(f"Could not read the input as {frm.upper()}", 422,
                   "The data does not look like that format — check the input format "
                   f"selector matches the file. OpenBabel said: {raw[:600]}")
    return err("Conversion failed", 422, raw)


# ────────────────────────────────────────────── 路由
_STATIC_CACHE = {}


@app.get("/<path:filename>")
def serve_static(filename):
    """自实现静态文件路由：gzip 压缩 + ETag + 1 天缓存"""
    root = os.path.join(BASE_DIR, "static")
    full = os.path.abspath(os.path.join(root, filename))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        abort(404)

    mtime = int(os.path.getmtime(full))
    cached = _STATIC_CACHE.get(full)
    if not cached or cached[0] != mtime:
        with open(full, "rb") as fh:
            raw = fh.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".js"):
            ctype = "application/javascript"
        elif full.endswith(".css"):
            ctype = "text/css"
        elif full.endswith(".svg"):
            ctype = "image/svg+xml"
        _STATIC_CACHE[full] = (mtime, raw, gzip.compress(raw, 6), ctype)
        cached = _STATIC_CACHE[full]

    mtime, raw, gz, ctype = cached
    etag = f'"{mtime}-{len(raw)}"'
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304)

    use_gzip = "gzip" in request.headers.get("Accept-Encoding", "") and len(raw) > 500
    resp = Response(gz if use_gzip else raw, mimetype=ctype)
    if use_gzip:
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    resp.headers["ETag"] = etag
    return resp


PAGE_META = {
    "index": {
        "page": "home",
        "template": "index.html",
        "title": "SeqChem — Free Chemistry & Bioinformatics Tools (SMILES, FASTA)",
        "description": "Free online chemistry and bioinformatics tools: convert SMILES, InChI, "
                       "MOL, SDF and PDB, calculate molecular properties, draw structures, generate "
                       "3D conformers and process FASTA/FASTQ sequences.",
    },
    "convert": {
        "page": "convert",
        "template": "convert.html",
        "title": "Chemical File Format Converter — SMILES, InChI, MOL, SDF, PDB",
        "description": "Convert chemical file formats online: SMILES to InChI, SDF to SMILES, "
                       "MOL to PDB, SMILES to 3D SDF and 190+ more formats, free and without registration.",
    },
    "properties": {
        "page": "properties",
        "template": "properties.html",
        "title": "Molecular Property Calculator — MW, logP, TPSA, HBD, HBA",
        "description": "Calculate molecular weight, molecular formula, logP, TPSA, hydrogen bond "
                       "donors and acceptors, rotatable bonds, InChI and InChIKey from SMILES.",
    },
    "depict": {
        "page": "depict",
        "template": "depict.html",
        "title": "2D Structure Generator — Draw Molecules from SMILES (SVG)",
        "description": "Draw a 2D chemical structure from SMILES or InChI and download it as a "
                       "scalable SVG image. Free online molecule drawing tool.",
    },
    "3d": {
        "page": "3d",
        "template": "three_d.html",
        "title": "3D Molecular Structure Generator — SMILES to 3D Conformer",
        "description": "Generate an interactive 3D molecular conformer from SMILES with OpenBabel "
                       "force-field optimisation, rotate it in your browser and download it as SDF.",
    },
    "substructure": {
        "page": "substructure",
        "template": "substructure.html",
        "title": "SMARTS Substructure Search — Filter Molecules by Pattern",
        "description": "Search a list of molecules for a SMARTS substructure pattern online. "
                       "Filter compound libraries by functional group, ring or atom type.",
    },
    "similarity": {
        "page": "similarity",
        "template": "similarity.html",
        "title": "Molecular Similarity — Tanimoto Coefficient Calculator",
        "description": "Compute Tanimoto similarity between two molecules using FP2, FP3, FP4 "
                       "or MACCS fingerprints. Free online molecular similarity calculator.",
    },
}


CREDITS = {
    "index": "chemistry by OpenBabel · IUPAC names by OPSIN · sequences in Python",
    "formula": "formula parsing in Python · structures by OpenBabel",
    "iupac": "name parsing by OPSIN with PubChem fallback · depiction by OpenBabel",
    "bio": "sequence tools implemented in Python",
}
DEFAULT_CREDIT = "molecule tools powered by OpenBabel 3.1.1"


def _credit_for(key):
    if key.startswith("bio"):
        return CREDITS["bio"]
    return CREDITS.get(key, DEFAULT_CREDIT)


NAV_KEYS = {"convert", "properties", "depict", "3d", "substructure", "similarity",
            "lipinski", "batch", "formula", "bio", "iupac"}

PAGE_META.update({
    "smiles-to-inchi": {
        "page": "convert", "nav": "", "template": "smiles_to_inchi.html",
        "title": "SMILES to InChI Converter — Free Online Chemistry Tool",
        "description": "Convert a SMILES string to standard InChI and InChIKey online. "
                       "Canonical, IUPAC-standard identifier for database lookup and deduplication.",
        "h1": "SMILES to InChI Converter",
        "lead": "Turn a SMILES string into a standard InChI — the canonical, IUPAC-maintained "
                "identifier used by PubChem, ChEMBL and patent databases.",
        "from_fmt": "smi", "to_fmt": "inchi",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
    },
    "inchi-to-smiles": {
        "page": "convert", "nav": "", "template": "inchi_to_smiles.html",
        "title": "InChI to SMILES Converter — Free Online Chemistry Tool",
        "description": "Convert InChI identifiers back to SMILES strings online with OpenBabel. "
                       "Free, instant, no registration required.",
        "h1": "InChI to SMILES Converter",
        "lead": "Recover a usable SMILES string from an InChI identifier so you can feed it to "
                "a viewer, editor, model or script.",
        "from_fmt": "inchi", "to_fmt": "smi",
        "placeholder": "e.g. InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)",
    },
    "sdf-to-smiles": {
        "page": "convert", "nav": "", "template": "sdf_to_smiles.html",
        "title": "SDF to SMILES Converter — Free Online Chemistry Tool",
        "description": "Convert SDF and SD structure files to SMILES strings. Multi-record SDF "
                       "files are supported — one SMILES per molecule in the same order.",
        "h1": "SDF to SMILES Converter",
        "lead": "Flatten an SDF / SD compound library into one SMILES per molecule. Paste a "
                "multi-record file or upload it — the order is preserved.",
        "from_fmt": "sdf", "to_fmt": "smi",
        "placeholder": "Paste SDF records (separated by $$$$) or upload a .sdf file",
    },
    "mol-to-smiles": {
        "page": "convert", "nav": "", "template": "mol_to_smiles.html",
        "title": "MOL to SMILES Converter — Free Online Chemistry Tool",
        "description": "Convert MDL MOL files to SMILES strings online. Works with MOL files "
                       "exported from ChemDraw, Marvin, Avogadro and most drawing tools.",
        "h1": "MOL to SMILES Converter",
        "lead": "Convert a single-molecule MDL MOL file into a SMILES string, ready for "
                "database search or modelling.",
        "from_fmt": "mol", "to_fmt": "smi",
        "placeholder": "Paste the contents of a .mol file or upload it",
    },
    "smiles-to-sdf": {
        "page": "convert", "nav": "", "template": "smiles_to_sdf.html",
        "title": "SMILES to SDF Converter — Free 3D Structure Generator",
        "description": "Convert SMILES to SDF structure files online, with optional 3D conformer "
                       "generation. Ready for docking, molecular viewers and modelling pipelines.",
        "h1": "SMILES to SDF Converter",
        "lead": "Generate an SDF structure file from SMILES. Check “3D coordinates” to get a "
                "force-field optimised conformer instead of a flat 2D layout.",
        "from_fmt": "smi", "to_fmt": "sdf",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
    },
    "smiles-to-png": {
        "page": "convert", "nav": "", "template": "smiles_to_png.html",
        "title": "SMILES to PNG — Draw Molecule Structure Images Online",
        "description": "Generate a PNG structure image from a SMILES string. Free online molecule "
                       "depiction tool, no registration required.",
        "h1": "SMILES to PNG",
        "lead": "Render a SMILES string as a 300 × 300 PNG structure image you can paste into a "
                "slide or a report.",
        "from_fmt": "smi", "to_fmt": "png",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
    },
    "lipinski": {
        "page": "lipinski", "template": "lipinski.html",
        "title": "Lipinski Rule of Five Calculator — Drug-likeness Checker",
        "description": "Check a molecule against Lipinski's rule of five and the Veber rules: "
                       "molecular weight, logP, hydrogen bond donors and acceptors, TPSA and "
                       "rotatable bonds.",
    },
})


# ---------------------------------------------------------------- 长尾转换页
FMT_LABEL = {
    "smi": "SMILES", "can": "SMILES", "inchi": "InChI", "inchikey": "InChIKey",
    "mol": "MOL", "sdf": "SDF", "mol2": "MOL2", "pdb": "PDB", "xyz": "XYZ",
    "cml": "CML", "png": "PNG", "svg": "SVG", "json": "JSON",
}
_PRESET_SLUGS = list(PRESETS)


def _fmt_label(fmt):
    return FMT_LABEL.get(fmt, fmt.upper())


def _preset_link(slug):
    cfg = PRESETS[slug]
    return {"slug": slug,
            "label": f'{_fmt_label(cfg["from_fmt"])} → {_fmt_label(cfg["to_fmt"])}'}


def _related_presets(slug):
    cfg = PRESETS[slug]
    same = [s for s in _PRESET_SLUGS if s != slug and
            (PRESETS[s]["from_fmt"] == cfg["from_fmt"] or PRESETS[s]["to_fmt"] == cfg["to_fmt"])]
    rest = [s for s in _PRESET_SLUGS if s != slug and s not in same]
    return [_preset_link(s) for s in (same + rest)[:6]]


for _slug, _cfg in PRESETS.items():
    PAGE_META[_slug] = {
        "page": "convert", "nav": "", "template": "preset.html",
        "title": _cfg["title"], "description": _cfg["description"],
        "h1": _cfg["h1"], "lead": _cfg["lead"],
        "from_fmt": _cfg["from_fmt"], "to_fmt": _cfg["to_fmt"],
        "placeholder": _cfg["placeholder"], "prose": _cfg["prose"],
        "gen3d_default": _cfg.get("gen3d_default", False),
        "related": _related_presets(_slug),
    }
    app.add_url_rule("/" + _slug, endpoint="preset_" + _slug.replace("-", "_"),
                     view_func=(lambda k=_slug: _render(k)))

# /convert 页面上的转换器目录（内链，帮助收录）
_CURATED = [
    ("smiles-to-inchi", "SMILES → InChI"),
    ("inchi-to-smiles", "InChI → SMILES"),
    ("sdf-to-smiles", "SDF → SMILES"),
    ("mol-to-smiles", "MOL → SMILES"),
    ("smiles-to-sdf", "SMILES → SDF"),
    ("smiles-to-png", "SMILES → PNG"),
]
PAGE_META["convert"]["converters"] = (
    [{"slug": s, "label": lb} for s, lb in _CURATED]
    + [_preset_link(s) for s in PRESETS]
)

PAGE_META["embed"] = {
    "page": "embed", "nav": "", "template": "embed_docs.html",
    "title": "Embed a Chemistry Converter — Free iframe Widget",
    "description": "Drop a working SMILES / InChI / MOL / SDF converter into your own site with one "
                   "iframe line. Free, no API key, no tracking of your readers.",
}

PAGE_META["api"] = {
    "page": "api", "nav": "", "template": "api_docs.html",
    "title": "Free Chemistry API — JSON Converter, Descriptors, Depiction",
    "description": "Free public JSON API for cheminformatics: convert 190+ chemical formats, "
                   "compute descriptors, draw structures, parse IUPAC names and process "
                   "FASTA/FASTQ. No API key, CORS enabled, OpenAPI spec included.",
}


def _base_url():
    return os.environ.get("BASE_URL", request.url_root).rstrip("/")


def _render(key):
    meta = dict(PAGE_META[key])
    template = meta.pop("template")
    meta.setdefault("nav", key if key in NAV_KEYS else "")
    # Use the URL actually being served: page keys and route paths differ for
    # iupac ("iupac" -> /iupac-to-structure) and bio ("bio" -> /bio/).
    path = "" if key == "index" else request.path
    page_name = "" if key == "index" else meta["title"].split("—")[0].strip()
    return render_template(template, canonical=_base_url() + path,
                           home_url=_base_url(), page_name=page_name,
                           credit=_credit_for(key), **meta)


@app.get("/")
def page_index():
    return _render("index")


@app.get("/convert")
def page_convert():
    return _render("convert")


@app.get("/properties")
def page_properties():
    return _render("properties")


@app.get("/depict")
def page_depict():
    return _render("depict")


@app.get("/3d")
def page_3d():
    return _render("3d")


@app.get("/substructure")
def page_substructure():
    return _render("substructure")


@app.get("/similarity")
def page_similarity():
    return _render("similarity")


@app.get("/smiles-to-inchi")
def page_smiles_to_inchi():
    return _render("smiles-to-inchi")


@app.get("/inchi-to-smiles")
def page_inchi_to_smiles():
    return _render("inchi-to-smiles")


@app.get("/sdf-to-smiles")
def page_sdf_to_smiles():
    return _render("sdf-to-smiles")


@app.get("/mol-to-smiles")
def page_mol_to_smiles():
    return _render("mol-to-smiles")


@app.get("/smiles-to-sdf")
def page_smiles_to_sdf():
    return _render("smiles-to-sdf")


@app.get("/smiles-to-png")
def page_smiles_to_png():
    return _render("smiles-to-png")


@app.get("/lipinski")
def page_lipinski():
    return _render("lipinski")




BIO_PAGES = {
    "bio-fasta-to-fastq": {
        "path": "/bio/fasta-to-fastq", "op": "fasta2fastq", "template": "bio_fasta_to_fastq.html",
        "title": "FASTA to FASTQ Converter — Free Online Bioinformatics Tool",
        "description": "Convert FASTA sequences to FASTQ format by adding placeholder quality scores. "
                       "Free online bioinformatics converter, multi-record files supported.",
        "h1": "FASTA to FASTQ Converter",
        "lead": "Add a uniform quality score to every base so your FASTA file becomes valid FASTQ "
                "that any sequencing pipeline will accept.",
        "input_label": "FASTA input", "action": "Convert to FASTQ", "show_frame": False,
        "placeholder": ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
    },
    "bio-fastq-to-fasta": {
        "path": "/bio/fastq-to-fasta", "op": "fastq2fasta", "template": "bio_fastq_to_fasta.html",
        "title": "FASTQ to FASTA Converter — Free Online Bioinformatics Tool",
        "description": "Convert FASTQ sequencing reads to FASTA by removing quality scores. "
                       "Free online bioinformatics tool, multi-record files supported.",
        "h1": "FASTQ to FASTA Converter",
        "lead": "Strip per-base quality scores from sequencing reads and keep clean FASTA "
                "sequences for alignment, assembly or BLAST.",
        "input_label": "FASTQ input", "action": "Convert to FASTA", "show_frame": False,
        "placeholder": "@read1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG\n+\nIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",
    },
    "bio-gc-content": {
        "path": "/bio/gc-content", "op": "stats", "template": "bio_gc_content.html",
        "title": "GC Content Calculator — Sequence Statistics Online",
        "description": "Calculate GC content, AT content, sequence length, N count and GC/AT skew "
                       "for DNA sequences. Free online bioinformatics calculator.",
        "h1": "GC Content Calculator",
        "lead": "Get GC content, AT content, length, ambiguous base count and skew statistics for "
                "each sequence in a FASTA file.",
        "input_label": "FASTA input", "action": "Calculate statistics", "show_frame": False,
        "placeholder": ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
    },
    "bio-reverse-complement": {
        "path": "/bio/reverse-complement", "op": "revcomp", "template": "bio_reverse_complement.html",
        "title": "Reverse Complement Tool — DNA Sequence Converter",
        "description": "Compute the reverse complement of DNA sequences online. Supports IUPAC "
                       "ambiguity codes and multi-record FASTA input.",
        "h1": "Reverse Complement",
        "lead": "Get the reverse complement of one or many DNA sequences, with IUPAC ambiguity "
                "codes handled correctly.",
        "input_label": "DNA sequence or FASTA", "action": "Reverse complement", "show_frame": False,
        "placeholder": "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
    },
    "bio-translate": {
        "path": "/bio/translate", "op": "translate", "template": "bio_translate.html",
        "title": "DNA to Protein Translation — Codon Translator",
        "description": "Translate DNA or RNA sequences to amino acids in all three reading frames "
                       "using the standard genetic code. Free online codon translator.",
        "h1": "DNA to Protein Translation",
        "lead": "Translate nucleotide sequences into amino acid chains using the standard genetic "
                "code. Choose the reading frame to try the three forward frames.",
        "input_label": "DNA or RNA sequence", "action": "Translate", "show_frame": True,
        "placeholder": ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
    },
}

PAGE_META.update({
    "batch": {
        "page": "batch", "template": "batch.html",
        "title": "Batch Chemical Format Converter — Convert Hundreds of Molecules",
        "description": "Convert SDF, SMILES or MOL files in bulk. Upload a compound library and "
                       "get the whole file converted to another chemical format in one run.",
    },
    "formula": {
        "page": "formula", "template": "formula.html",
        "title": "Molecular Formula and Weight Calculator",
        "description": "Calculate molecular weight and elemental composition from a chemical "
                       "formula, or get formula and weight from a SMILES string.",
    },
    "iupac": {
        "page": "iupac", "template": "iupac.html",
        "title": "IUPAC Name to Structure — Chemical Structure Generator",
        "description": "Convert an IUPAC chemical name into a structure: SMILES, InChI, "
                       "InChIKey and a drawn 2D image. Powered by OPSIN with a PubChem fallback.",
    },
    "bio": {
        "page": "bio", "template": "bio_index.html",
        "title": "FASTA / FASTQ Sequence Tools — Free Bioinformatics Utilities",
        "description": "Free online bioinformatics tools: FASTA to FASTQ, FASTQ to FASTA, GC "
                       "content, reverse complement and DNA to protein translation.",
    },
})


def _bio_view(key):
    cfg = dict(BIO_PAGES[key])
    path = cfg.pop("path")
    template = cfg.pop("template")
    page_name = cfg["title"].split("—")[0].strip()
    return render_template(template, canonical=_base_url() + path, page="bio", nav="bio",
                           home_url=_base_url(), page_name=page_name,
                           credit=CREDITS["bio"], **cfg)


for _key, _cfg in BIO_PAGES.items():
    app.add_url_rule(_cfg["path"], endpoint=_key.replace("-", "_"), view_func=(lambda k=_key: _bio_view(k)))


@app.get("/batch")
def page_batch():
    return _render("batch")


@app.get("/formula")
def page_formula():
    return _render("formula")


@app.get("/iupac-to-structure")
def page_iupac():
    return _render("iupac")


@app.get("/bio/")
def page_bio_index():
    return _render("bio")


# ---------------------------------------------------------------- 教程文章
GUIDE_DATE = "2026-11-11"


def _guide_view(slug):
    g = GUIDES[slug]
    return render_template("guide.html", canonical=_base_url() + g["path"],
                           home_url=_base_url(), page="guides", nav="",
                           page_name=g["h1"], credit=_credit_for("index"),
                           h1=g["h1"], title=g["title"], description=g["description"],
                           lead=g["lead"], prose=g["prose"], related=g["related"],
                           published=GUIDE_DATE)


for _slug, _g in GUIDES.items():
    app.add_url_rule(_g["path"], endpoint="guide_" + _slug.replace("-", "_"),
                     view_func=(lambda k=_slug: _guide_view(k)))


@app.get("/guides/")
def page_guides_index():
    return render_template("guides_index.html",
                           canonical=_base_url() + GUIDE_INDEX["path"],
                           home_url=_base_url(), page="guides", nav="",
                           page_name=GUIDE_INDEX["h1"], credit=_credit_for("index"),
                           title=GUIDE_INDEX["title"],
                           description=GUIDE_INDEX["description"],
                           guides=[{"path": g["path"], "h1": g["h1"], "lead": g["lead"]}
                                   for g in GUIDES.values()])


# ---------------------------------------------------------------- 可嵌入组件
EMBED_TARGETS = ["can", "inchi", "inchikey", "mol", "sdf", "mol2", "pdb", "xyz", "cml", "svg", "png"]
EMBED_LABELS = {
    "can": "SMILES (canonical)", "inchi": "InChI", "inchikey": "InChIKey",
    "mol": "MOL", "sdf": "SDF", "mol2": "MOL2", "pdb": "PDB", "xyz": "XYZ",
    "cml": "CML", "svg": "SVG image", "png": "PNG image",
}


@app.get("/embed")
def page_embed():
    return _render("embed")


@app.get("/embed/convert")
def page_embed_convert():
    frm = (request.args.get("from") or "").strip() or "smi"
    to = (request.args.get("to") or "").strip() or "mol"
    if not valid_format(frm):
        frm = "smi"
    if to not in EMBED_TARGETS:
        to = "mol"
    title = (request.args.get("title") or "").strip()[:80]
    if not title:
        title = f"{FMT_LABEL.get(frm, frm.upper())} → {EMBED_LABELS.get(to, to.upper())}"
    return render_template(
        "embed_widget.html", title=title, from_fmt=frm, to_fmt=to,
        to_options=[{"id": f, "label": EMBED_LABELS[f]} for f in EMBED_TARGETS],
        placeholder="e.g. CC(=O)Oc1ccccc1C(=O)O",
        home_url=_base_url(),
    )


@app.get("/llms.txt")
def llms_txt():
    """Summary for LLM crawlers and agent tooling (https://llmstxt.org)."""
    base = _base_url()
    out = [
        "# SeqChem",
        "",
        "> Free online chemistry and bioinformatics tools. Convert between 190+ chemical formats, "
        "compute molecular descriptors, draw 2D structures, generate 3D conformers, run SMARTS "
        "substructure and Tanimoto similarity searches, resolve IUPAC names, and process "
        "FASTA/FASTQ sequences. No account, no paywall. Everything runs server-side through "
        "OpenBabel; the sequence tools are implemented in Python.",
        "",
        "## Core tools",
    ]
    core = [
        ("/convert", "Format converter", "Any OpenBabel-readable format to any writable one."),
        ("/properties", "Molecular properties", "Formula, MW, logP, TPSA, HBD, HBA, rotatable bonds, InChI, InChIKey."),
        ("/depict", "2D depiction", "Render a SMILES or InChI as a scalable SVG structure."),
        ("/3d", "3D structure", "Generate a force-field optimised conformer and view it in the browser."),
        ("/substructure", "Substructure search", "Filter a molecule list by a SMARTS pattern."),
        ("/similarity", "Molecular similarity", "Tanimoto coefficient over FP2, FP3, FP4 or MACCS."),
        ("/lipinski", "Drug-likeness", "Lipinski rule of five plus Veber criteria."),
        ("/batch", "Batch converter", "Whole compound libraries, up to 5,000 records per run."),
        ("/formula", "Formula calculator", "Molecular weight and composition from a formula or a structure."),
        ("/iupac-to-structure", "IUPAC name to structure", "OPSIN parsing with SMILES, InChI and InChIKey output."),
    ]
    for path, name, desc in core:
        out.append(f"- [{name}]({base}{path}): {desc}")

    out += ["", "## One-click converters"]
    for slug, cfg in PRESETS.items():
        label = f'{_fmt_label(cfg["from_fmt"])} to {_fmt_label(cfg["to_fmt"])}'
        out.append(f"- [{label}]({base}/{slug})")

    out += ["", "## Sequence tools"]
    for key, cfg in BIO_PAGES.items():
        name = cfg["title"].split("—")[0].strip()
        out.append(f"- [{name}]({base}{cfg['path']})")

    out += ["", "## Guides"]
    for key, g in GUIDES.items():
        out.append(f"- [{g['h1']}]({base}{g['path']})")

    out += [
        "",
        "## API",
        f"- [API documentation]({base}/api): JSON endpoints for conversion, descriptors, depiction, "
        "3D generation, substructure, similarity, IUPAC names, batch and FASTA/FASTQ.",
        f"- [OpenAPI 3.0 spec]({base}/api/openapi.json)",
        f"- [Embeddable converter]({base}/embed): one-line iframe widget",
        "",
        "## Notes",
        "- All endpoints are free and keyless; fair use is 120 requests/minute per client.",
        "- Batch limit: 64 MB input, 5,000 records (500 when the output is an image).",
        "- Chemistry engine: OpenBabel 3.1.1. Name parsing: OPSIN. 3D rendering: 3Dmol.js.",
        "",
    ]
    return Response("\n".join(out), mimetype="text/plain")


@app.get("/robots.txt")
def robots():
    base = _base_url()
    body = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    base = _base_url()
    entries = [
        ("", "1.0", "weekly"),
        ("/convert", "0.9", "monthly"),
        ("/properties", "0.9", "monthly"),
        ("/depict", "0.9", "monthly"),
        ("/3d", "0.9", "monthly"),
        ("/substructure", "0.8", "monthly"),
        ("/similarity", "0.8", "monthly"),
        ("/smiles-to-inchi", "0.8", "monthly"),
        ("/inchi-to-smiles", "0.8", "monthly"),
        ("/sdf-to-smiles", "0.8", "monthly"),
        ("/mol-to-smiles", "0.8", "monthly"),
        ("/smiles-to-sdf", "0.8", "monthly"),
        ("/smiles-to-png", "0.8", "monthly"),
        ("/lipinski", "0.8", "monthly"),
        ("/batch", "0.8", "monthly"),
        ("/formula", "0.9", "monthly"),
        ("/iupac-to-structure", "0.9", "monthly"),
        ("/bio/", "0.8", "weekly"),
        ("/bio/fasta-to-fastq", "0.8", "monthly"),
        ("/bio/fastq-to-fasta", "0.8", "monthly"),
        ("/bio/gc-content", "0.8", "monthly"),
        ("/bio/reverse-complement", "0.8", "monthly"),
        ("/bio/translate", "0.8", "monthly"),
        ("/guides/", "0.8", "monthly"),
        ("/guides/smiles-inchi-inchikey", "0.8", "monthly"),
        ("/guides/lipinski-rule-of-five", "0.8", "monthly"),
        ("/guides/fasta-vs-fastq", "0.8", "monthly"),
        ("/api", "0.8", "monthly"),
        ("/embed", "0.7", "monthly"),
    ]
    entries += [(f"/{slug}", "0.7", "monthly") for slug in PRESETS]
    import datetime
    today = datetime.date.today().isoformat()
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path, prio, freq in entries:
        body += (f"  <url><loc>{base}{path}</loc><lastmod>{today}</lastmod>"
                 f"<priority>{prio}</priority><changefreq>{freq}</changefreq></url>\n")
    body += "</urlset>\n"
    return Response(body, mimetype="application/xml")


@app.get("/health")
def health():
    return jsonify({"ok": True, "formats": len(supported_formats())})


@app.get("/api/formats")
def api_formats():
    formats = supported_formats()
    common = [
        "smi", "can", "inchi", "inchikey", "mol", "sdf", "mol2", "pdb",
        "xyz", "cml", "sdf", "json", "smi", "txt", "svg", "png",
    ]
    items = [
        {"id": k, "desc": v["desc"], "read": v["read"], "write": v["write"]}
        for k, v in sorted(formats.items())
    ]
    order = {k: i for i, k in enumerate(dict.fromkeys(common))}
    items.sort(key=lambda x: (order.get(x["id"], 999), x["id"]))
    return jsonify({"ok": True, "items": items})


@app.get("/api/example")
def api_example():
    """Generate an example molecule (aspirin) in the requested format"""
    fmt = request.args.get("format", "smi")
    if not valid_format(fmt):
        return err("Unsupported format")
    if fmt in MIME_BY_FORMAT and not MIME_BY_FORMAT[fmt].startswith("text/"):
        fmt = "smi"

    args = ["-ismi", f"-o{fmt}"]
    if fmt in THREE_D_FORMATS:
        args.append("--gen3d")

    rc, out, _ = run_obabel(args, EXAMPLE_SMILES.encode("utf-8"), timeout=90)
    if rc != 0 or not out:
        return err("Failed to generate example")
    try:
        return jsonify({"ok": True, "format": fmt, "data": out.decode("utf-8")})
    except UnicodeDecodeError:
        return err("This format has no text example")


@app.post("/api/convert")
def api_convert():
    try:
        data, text = payload()
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "smi"
    to = (data.get("to") or "").strip() or "mol"
    opts = [o for o in (data.get("opts") or []) if isinstance(o, str)][:10]

    if not valid_format(frm) or not valid_format(to):
        return err("Unsupported format")
    if not text.strip():
        return err("Please enter molecule data")

    allowed_opts = {
        "--gen3d", "--canonical", "-h", "--addhydrogens", "--deletehydrogens",
        "--unique", "--separate", "--errorlevel", "--title",
    }
    safe_opts = [o for o in opts if o.split("=")[0] in allowed_opts]

    # Auto-add --gen3d for 3D formats, otherwise output would be flat
    if to in THREE_D_FORMATS and "--gen3d" not in safe_opts:
        safe_opts.append("--gen3d")

    rc, out, errtext = run_obabel(
        [f"-i{frm}", f"-o{to}"] + safe_opts,
        text.encode("utf-8"),
        timeout=180 if to in THREE_D_FORMATS else TIMEOUT,
    )
    if rc != 0 or not out:
        return _obabel_error(frm, errtext)

    # Build an SDF preview for 3D formats (3Dmol cannot render stl/obj meshes)
    preview_sdf = None
    if to in THREE_D_FORMATS:
        preview_args = [f"-i{frm}", "-osdf"]
        if frm in TWO_D_SOURCES:
            preview_args.append("--gen3d")
        rc2, out2, _ = run_obabel(preview_args, text.encode("utf-8"), timeout=180)
        if rc2 == 0 and out2:
            preview_sdf = out2.decode("utf-8", "replace")

    mime = MIME_BY_FORMAT.get(to, "application/octet-stream")
    try:
        decoded = out.decode("utf-8")
        binary = False
    except UnicodeDecodeError:
        decoded = None
        binary = True

    if binary:
        b64 = base64.b64encode(out).decode("ascii")
        return jsonify({
            "ok": True,
            "binary": True,
            "mime": mime,
            "data_url": f"data:{mime};base64,{b64}",
            "size": len(out),
            "preview_sdf": preview_sdf,
            "log": errtext.strip()[:2000],
        })

    return jsonify({
        "ok": True,
        "binary": False,
        "result": decoded,
        "mime": mime,
        "is_image": mime.startswith("image/"),
        "preview_sdf": preview_sdf,
        "log": errtext.strip()[:2000],
    })


DESCRIPTORS = [
    ("formula", "Formula"),
    ("MW", "Molecular weight"),
    ("logP", "logP"),
    ("TPSA", "TPSA"),
    ("HBD", "H-bond donors"),
    ("HBA1", "H-bond acceptors"),
    ("rotors", "Rotatable bonds"),
    ("atoms", "Atoms"),
    ("bonds", "Bonds"),
    ("MR", "Molar refractivity"),
    ("cansmi", "Canonical SMILES"),
    ("InChI", "InChI"),
    ("InChIKey", "InChIKey"),
]


@app.post("/api/properties")
def api_properties():
    try:
        data, text = payload()
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "smi"
    if not valid_format(frm):
        return err("Unsupported input format")
    if not text.strip():
        return err("Please enter molecule data")

    names = " ".join(k for k, _ in DESCRIPTORS)
    rc, out, errtext = run_obabel(
        [f"-i{frm}", "-osmi", "--append", names], text.encode("utf-8")
    )
    if rc != 0 or not out:
        return err("Calculation failed", 422, errtext.strip()[:2000] or "No output")

    lines = [l for l in out.decode("utf-8", "replace").splitlines() if l.strip()]
    rows = []
    for line in lines:
        parts = line.split("\t")
        if not parts:
            continue
        smiles = parts[0]
        values = parts[1].split(" ") if len(parts) > 1 else []
        row = {"smiles": smiles, "props": {}}
        for i, (key, _label) in enumerate(DESCRIPTORS):
            row["props"][key] = values[i] if i < len(values) else ""
        rows.append(row)

    return jsonify({
        "ok": True,
        "rows": rows,
        "labels": {k: label for k, label in DESCRIPTORS},
        "log": errtext.strip()[:1000],
    })


@app.post("/api/depict")
def api_depict():
    try:
        data, text = payload()
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "smi"
    if not valid_format(frm) or not text.strip():
        return err("Please enter valid molecule data")

    rc, out, errtext = run_obabel([f"-i{frm}", "-osvg", "-xC"], text.encode("utf-8"))
    if rc != 0 or not out:
        return err("Failed to generate structure", 422, errtext.strip()[:2000] or "No output")

    svg = out.decode("utf-8", "replace")
    return jsonify({"ok": True, "svg": svg})


@app.post("/api/gen3d")
def api_gen3d():
    try:
        data, text = payload()
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "smi"
    if not valid_format(frm) or not text.strip():
        return err("Please enter valid molecule data")

    if not HEAVY_SLOTS.acquire(timeout=HEAVY_WAIT_SECONDS):
        return heavy_busy()
    try:
        rc, out, errtext = run_obabel(
            [f"-i{frm}", "-osdf", "--gen3d"], text.encode("utf-8"), timeout=120
        )
    finally:
        HEAVY_SLOTS.release()
    if rc != 0 or not out:
        return err("3D generation failed", 422, errtext.strip()[:2000] or "No output")

    return jsonify({"ok": True, "result": out.decode("utf-8", "replace")})


@app.post("/api/substructure")
def api_substructure():
    try:
        data, text = payload()
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "smi"
    smarts = (data.get("smarts") or "").strip()
    if not valid_format(frm):
        return err("Unsupported input format")
    if not text.strip():
        return err("Please enter molecule data")
    if not smarts:
        return err("Please enter a SMARTS pattern")
    if len(smarts) > 500:
        return err("SMARTS pattern too long")

    rc, out, errtext = run_obabel(
        [f"-i{frm}", "-osmi", "-s", smarts], text.encode("utf-8")
    )
    matched = [l.strip() for l in out.decode("utf-8", "replace").splitlines() if l.strip()]

    return jsonify({
        "ok": True,
        "count": len(matched),
        "matches": matched[:500],
        "log": errtext.strip()[:1000],
    })


@app.post("/api/fingerprint")
def api_fingerprint():
    try:
        data, text = payload()
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "smi"
    fp = data.get("fp", "FP2")
    if fp not in {"FP2", "FP3", "FP4", "MACCS", "ECFP2", "ECFP4", "ECFP6"}:
        return err("Unsupported fingerprint type")
    if not valid_format(frm) or not text.strip():
        return err("Please enter valid molecule data")

    rc, out, errtext = run_obabel(
        [f"-i{frm}", "-ofpt", "-xf", fp], text.encode("utf-8")
    )
    if rc != 0 or not out:
        return err("指纹Calculation failed", 422, errtext.strip()[:2000] or "No output")

    raw = out.decode("utf-8", "replace")
    bits = len(re.findall(r"[0-9a-fA-F]{8}", raw))
    return jsonify({"ok": True, "result": raw, "words": bits})


@app.post("/api/similarity")
def api_similarity():
    try:
        data, _ = payload()
    except ValueError as exc:
        return err(str(exc))

    a = (data.get("a") or "").strip()
    b = (data.get("b") or "").strip()
    frm = (data.get("from") or "").strip() or "smi"
    fp = data.get("fp", "FP2")
    if not a or not b:
        return err("Both molecules are required")
    if fp not in {"FP2", "FP3", "FP4", "MACCS"}:
        return err("Unsupported fingerprint type")

    def bits_of(smiles):
        rc, out, _ = run_obabel(
            [f"-i{frm}", "-ofpt", "-xf", fp], smiles.encode("utf-8")
        )
        if rc != 0 or not out:
            return None
        words = re.findall(r"[0-9a-fA-F]{8}", out.decode("utf-8", "replace"))
        value = 0
        for i, w in enumerate(words):
            value |= int(w, 16) << (32 * i)
        return value

    x, y = bits_of(a), bits_of(b)
    if x is None or y is None:
        return err("Could not parse one of the molecules")

    inter = bin(x & y).count("1")
    union = bin(x | y).count("1")
    tanimoto = inter / union if union else 0.0

    return jsonify({
        "ok": True,
        "tanimoto": round(tanimoto, 4),
        "bits_a": bin(x).count("1"),
        "bits_b": bin(y).count("1"),
        "common": inter,
        "union": union,
    })


# ────────────────────────────────────────────── IUPAC 名称解析（OPSIN）
@app.post("/api/iupac")
def api_iupac():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return err("Please enter an IUPAC name")
    if len(name) > 300:
        return err("Name too long")

    url = "https://opsin.ch.cam.ac.uk/opsin/" + urllib.parse.quote(name) + ".json"
    req = urllib.request.Request(url, headers={"User-Agent": "SeqChem/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        # OPSIN 解析失败时返回 404，但 body 仍是 JSON
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return err("OPSIN lookup failed", 502, str(exc)[:300])
    except Exception as exc:  # noqa: BLE001
        return err("OPSIN lookup failed", 502, str(exc)[:300])

    if payload.get("status") != "SUCCESS":
        return jsonify({
            "ok": True, "resolved": False, "source": "opsin",
            "message": payload.get("message", "Name could not be interpreted"),
        })

    return jsonify({
        "ok": True,
        "resolved": True,
        "source": "opsin",
        "smiles": payload.get("smiles") or "",
        "inchi": payload.get("stdinchi") or payload.get("inchi") or "",
        "inchikey": payload.get("stdinchikey") or "",
    })


# ────────────────────────────────────────────── 批量转换
def split_records(text: str, frm: str):
    """把多分子输入拆成单条记录，用于逐条生成图片"""
    text = text.strip()
    if frm in {"sdf", "sd"}:
        parts = [p.strip() for p in re.split(r"\$\$\$\$", text) if p.strip()]
        return [p + "\n$$$$\n" for p in parts]
    if frm in {"smi", "can", "smiles", "inchi", "inchikey", "txt"}:
        return [line.strip() for line in text.splitlines() if line.strip()]
    return [text]


@app.post("/api/batch")
def api_batch():
    try:
        data, text = payload(MAX_BATCH_INPUT)
    except ValueError as exc:
        return err(str(exc))

    frm = (data.get("from") or "").strip() or "sdf"
    to = (data.get("to") or "").strip() or "smi"
    if not valid_format(frm) or not valid_format(to):
        return err("Unsupported format")
    if not text.strip():
        return err("Please enter molecule data")

    opts = [o for o in (data.get("opts") or []) if isinstance(o, str)][:10]
    allowed = {"--canonical", "--unique", "--deletehydrogens", "--addhydrogens"}
    safe = [o for o in opts if o.split("=")[0] in allowed]

    # 明确的批量上限：先数记录数再跑 OpenBabel，避免大文件跑到一半才失败
    count = len(split_records(text, frm))
    is_image = to in MIME_BY_FORMAT
    limit = MAX_BATCH_IMAGES if is_image else MAX_BATCH_RECORDS
    if count > limit:
        what = "image output" if is_image else "records"
        hint = ("Each image is rendered in a separate pass — convert in smaller batches, "
                "or output SDF/SMILES instead.") if is_image else \
               "Split the file into several smaller batches and run them separately."
        return err(f"Batch limit exceeded: {count} records, maximum {limit} per run "
                   f"({what})", 400, hint)

    if not HEAVY_SLOTS.acquire(timeout=HEAVY_WAIT_SECONDS):
        return err("Server is busy converting another large file", 429,
                   f"Large jobs run one at a time. Please retry in about "
                   f"{HEAVY_WAIT_SECONDS} seconds.",
                   )

    rc, out, errtext = run_obabel(
        [f"-i{frm}", f"-o{to}"] + safe, text.encode("utf-8"), timeout=1500
    )
    try:
        if rc != 0 or not out:
            return _obabel_error(frm, errtext)
        return _batch_response(frm, to, text, out, errtext, safe)
    finally:
        HEAVY_SLOTS.release()


def _batch_response(frm, to, text, out, errtext, safe):

    m = re.search(r"(\d+)\s+molecules? converted", errtext)
    converted = int(m.group(1)) if m else 0

    # 图片格式：批量导出会得到多个二进制文件拼接，无法直接展示
    mime = MIME_BY_FORMAT.get(to)
    if mime:
        all_records = split_records(text, frm)
        if len(all_records) <= 1:
            b64 = base64.b64encode(out).decode("ascii")
            return jsonify({
                "ok": True, "binary": True, "mime": mime,
                "data_url": f"data:{mime};base64,{b64}",
                "converted": converted, "log": errtext.strip()[:2000],
            })

        # 多条记录：逐条转换后打包成 ZIP
        records = all_records
        images, failed = [], 0
        for rec in records:
            rc1, out1, _ = run_obabel(
                [f"-i{frm}", f"-o{to}"] + safe, rec.encode("utf-8"), timeout=60
            )
            if rc1 == 0 and out1:
                images.append(out1)
            else:
                failed += 1

        if not images:
            return err(f"Could not convert any molecule to {to}", 422)

        ext = to
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(images, 1):
                zf.writestr(f"molecule-{i:03d}.{ext}", img)
        zip_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        previews = []
        if mime.startswith("image/"):
            previews = [
                f"data:{mime};base64,{base64.b64encode(img).decode('ascii')}"
                for img in images[:6]
            ]

        return jsonify({
            "ok": True,
            "binary": True,
            "mime": "application/zip",
            "zip_url": f"data:application/zip;base64,{zip_b64}",
            "previews": previews,
            "rendered": len(images),
            "failed": failed,
            "converted": converted,
            "log": errtext.strip()[:2000],
        })

    return jsonify({
        "ok": True,
        "binary": False,
        "result": out.decode("utf-8", "replace"),
        "converted": converted,
        "log": errtext.strip()[:2000],
    })


# ────────────────────────────────────────────── 分子式
@app.post("/api/formula")
def api_formula():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "formula")

    if mode == "structure":
        text = (data.get("data") or "").strip()
        frm = (data.get("from") or "").strip() or "smi"
        if not text:
            return err("Please enter molecule data")
        if not valid_format(frm):
            return err("Unsupported format")
        rc, out, e = run_obabel([f"-i{frm}", "-osmi", "--append", "formula MW"], text.encode())
        if rc != 0 or not out:
            return err("Calculation failed", 422, e.strip()[:1000] or "No output")
        rows = []
        for line in out.decode("utf-8", "replace").splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            vals = parts[1].split(" ")
            rows.append({
                "smiles": parts[0],
                "formula": vals[0] if len(vals) > 0 else "",
                "mw": round(float(vals[1]), 3) if len(vals) > 1 and vals[1] else None,
            })
        if not rows:
            return err("Could not parse the input")
        return jsonify({"ok": True, "rows": rows})

    formula = (data.get("formula") or "").strip()
    if not formula:
        return err("Please enter a molecular formula")
    try:
        counts = parse_formula(formula)
    except FormulaError as exc:
        return err(str(exc))

    return jsonify({
        "ok": True,
        "formula": hill_notation(counts),
        "mw": round(molecular_weight(counts), 3),
        "composition": composition(counts),
        "atoms": sum(counts.values()),
    })


# ────────────────────────────────────────────── FASTA / FASTQ
@app.post("/api/bio")
def api_bio():
    data = request.get_json(silent=True) or {}
    op = data.get("op", "")
    text = (data.get("data") or "").strip()
    if not text:
        return err("Please enter sequence data")

    try:
        if op == "fasta2fastq":
            records = parse_fasta(text)
            if not records:
                return err("No FASTA records found")
            return jsonify({"ok": True, "result": fasta_to_fastq(text), "count": len(records)})

        if op == "fastq2fasta":
            records = parse_fastq(text)
            if not records:
                return err("No FASTQ records found")
            return jsonify({"ok": True, "result": fastq_to_fasta(text), "count": len(records)})

        if op == "revcomp":
            return jsonify({"ok": True, "result": reverse_complement(text)})

        if op == "translate":
            frame = int(data.get("frame", 0))
            return jsonify({"ok": True, "result": translate(text, frame)})

        if op == "stats":
            rows = sequence_stats(text)
            if not rows:
                return err("No sequence found")
            return jsonify({"ok": True, "rows": rows})

        return err("Unknown operation")
    except Exception as exc:  # noqa: BLE001
        return err("Processing failed", 422, str(exc)[:1000])


# ────────────────────────────────────────────── 公开 API 文档与版本化别名
@app.get("/api")
def page_api_docs():
    return _render("api")


_V1_ENDPOINTS = [
    ("formats", "get", api_formats),
    ("example", "get", api_example),
    ("convert", "post", api_convert),
    ("properties", "post", api_properties),
    ("depict", "post", api_depict),
    ("gen3d", "post", api_gen3d),
    ("substructure", "post", api_substructure),
    ("fingerprint", "post", api_fingerprint),
    ("similarity", "post", api_similarity),
    ("iupac", "post", api_iupac),
    ("batch", "post", api_batch),
    ("formula", "post", api_formula),
    ("bio", "post", api_bio),
]
for _name, _method, _fn in _V1_ENDPOINTS:
    app.add_url_rule(f"/api/v1/{_name}", endpoint=f"v1_{_name}",
                     view_func=_fn, methods=[_method.upper()])


def _openapi_spec():
    base = _base_url()

    def body(props, required=None):
        return {
            "required": True,
            "content": {"application/json": {"schema": {
                "type": "object", "properties": props,
                "required": required or [k for k in props if k in ("data", "name", "formula")],
            }}},
        }

    def ok(desc):
        return {"200": {"description": desc,
                        "content": {"application/json": {"schema": {"type": "object"}}}}}

    def op(op_id, summary, description="", request_body=None, params=None, tags=None):
        o = {"operationId": op_id, "summary": summary, "description": description,
             "tags": tags or ["chemistry"], "responses": {
                 **ok("Success"),
                 "400": {"description": "Invalid input"},
                 "422": {"description": "Conversion failed"},
                 "429": {"description": "Rate limit exceeded"}}}
        if request_body:
            o["requestBody"] = request_body
        if params:
            o["parameters"] = params
        return o

    q = lambda name, desc, schema=None: {  # noqa: E731
        "name": name, "in": "query", "required": False,
        "description": desc, "schema": schema or {"type": "string"}}

    data_prop = {"type": "string", "description": "Molecule or sequence data"}
    from_prop = {"type": "string", "default": "smi",
                 "description": "Input format id, see GET /api/v1/formats"}
    to_prop = {"type": "string", "default": "mol", "description": "Output format id"}
    opts_prop = {"type": "array", "items": {"type": "string"},
                 "description": "OpenBabel options, e.g. [\"--gen3d\", \"--canonical\"]"}

    paths = {
        "/api/v1/formats": {"get": op(
            "listFormats", "List supported formats",
            "Returns every format OpenBabel can read and/or write.", tags=["meta"],
            params=[q("dir", "Filter by direction: read, write, or both")])},
        "/api/v1/example": {"get": op(
            "example", "Get an example molecule",
            "Returns aspirin in the requested format, useful for testing.",
            tags=["meta"], params=[q("format", "Format id, default smi")])},
        "/api/v1/convert": {"post": op(
            "convert", "Convert between chemical formats",
            "Converts one or more records between any two OpenBabel formats. "
            "Binary outputs (PNG, PDF, STL) are returned base64-encoded.",
            request_body=body({"data": data_prop, "from": from_prop,
                               "to": to_prop, "opts": opts_prop}, ["data"]))},
        "/api/v1/properties": {"post": op(
            "properties", "Compute molecular descriptors",
            "Returns formula, MW, logP, TPSA, HBD, HBA, rotatable bonds, canonical SMILES, "
            "InChI and InChIKey for every record.",
            request_body=body({"data": data_prop, "from": from_prop}, ["data"]))},
        "/api/v1/depict": {"post": op(
            "depict", "Render a 2D structure as SVG",
            request_body=body({"data": data_prop, "from": from_prop}, ["data"]))},
        "/api/v1/gen3d": {"post": op(
            "gen3d", "Generate a 3D conformer",
            "Heavy endpoint — serialised across the server. Returns an SDF block.",
            request_body=body({"data": data_prop, "from": from_prop}, ["data"]))},
        "/api/v1/substructure": {"post": op(
            "substructure", "SMARTS substructure filter",
            request_body=body({"data": data_prop, "from": from_prop,
                               "smarts": {"type": "string"}}, ["data", "smarts"]))},
        "/api/v1/fingerprint": {"post": op(
            "fingerprint", "Compute a molecular fingerprint",
            request_body=body({"data": data_prop, "from": from_prop,
                               "fp": {"type": "string", "default": "FP2",
                                      "enum": ["FP2", "FP3", "FP4", "MACCS",
                                               "ECFP2", "ECFP4", "ECFP6"]}}, ["data"]))},
        "/api/v1/similarity": {"post": op(
            "similarity", "Tanimoto similarity between two molecules",
            request_body=body({"a": {"type": "string"}, "b": {"type": "string"},
                               "from": from_prop,
                               "fp": {"type": "string", "default": "FP2",
                                      "enum": ["FP2", "FP3", "FP4", "MACCS"]}},
                              ["a", "b"]))},
        "/api/v1/iupac": {"post": op(
            "iupac", "Resolve an IUPAC name to a structure",
            "Parses the name with OPSIN (Cambridge) and returns SMILES, InChI and InChIKey.",
            tags=["chemistry", "naming"],
            request_body=body({"name": {"type": "string"}}, ["name"]))},
        "/api/v1/batch": {"post": op(
            "batch", "Bulk conversion",
            "Converts a whole file. Limits: 64 MB input, 5000 records (500 for image output).",
            request_body=body({"data": data_prop, "from": from_prop,
                               "to": to_prop, "opts": opts_prop}, ["data"]))},
        "/api/v1/formula": {"post": op(
            "formula", "Molecular formula and weight",
            "Use mode=formula to parse a formula string, mode=structure to compute from a structure.",
            request_body=body({"mode": {"type": "string", "enum": ["formula", "structure"],
                                        "default": "formula"},
                               "formula": {"type": "string"},
                               "data": data_prop, "from": from_prop}))},
        "/api/v1/bio": {"post": op(
            "bio", "FASTA / FASTQ operations",
            "op is one of fasta2fastq, fastq2fasta, revcomp, translate, stats.",
            tags=["bioinformatics"],
            request_body=body({"op": {"type": "string",
                                      "enum": ["fasta2fastq", "fastq2fasta",
                                               "revcomp", "translate", "stats"]},
                               "data": data_prop,
                               "frame": {"type": "integer", "default": 0}}, ["op", "data"]))},
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "SeqChem API",
            "version": "1.0.0",
            "description": "Free JSON API for chemical format conversion, molecular descriptors, "
                           "2D depiction, 3D conformer generation, substructure and similarity "
                           "search, IUPAC name resolution and FASTA/FASTQ operations. "
                           "No API key required. Limits: 8 MB per request (64 MB batch), "
                           "120 requests/minute per client.",
            "license": {"name": "Free to use with attribution",
                        "url": base + "/api"},
            "contact": {"url": base + "/api", "email": "devin2xing@gmail.com"},
        },
        "servers": [{"url": base}],
        "tags": [
            {"name": "meta", "description": "Discovery and example data"},
            {"name": "chemistry", "description": "Structure conversion and analysis"},
            {"name": "naming", "description": "IUPAC name handling"},
            {"name": "bioinformatics", "description": "Sequence tools"},
        ],
        "paths": paths,
    }


@app.get("/api/openapi.json")
def api_openapi():
    return jsonify(_openapi_spec())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, threaded=True)
