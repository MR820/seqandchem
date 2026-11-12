#!/usr/bin/env python3
"""Cross-post the SeqChem guides to dev.to with a canonical link back to the site.

    python3 promo/publish_devto.py                 # preview
    python3 promo/publish_devto.py --publish       # publish everything
    python3 promo/publish_devto.py --publish --only fasta-vs-fastq

Needs a dev.to API key at ~/.config/seqchem/devto_token. dev.to rate-limits
article creation to roughly one every five minutes.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from markdownify import markdownify as md  # noqa: E402
from guides import GUIDES  # noqa: E402

BASE = "https://seqandchem.com"
TOKEN = open(os.path.expanduser("~/.config/seqchem/devto_token")).read().strip()

ARTICLES = [
    {
        "slug": "smiles-inchi-inchikey",
        "tags": ["chemistry", "cheminformatics", "opensource", "science"],
        "footer": "SeqChem has free browser tools for all of this: [SMILES to InChI]"
                  "(https://seqandchem.com/smiles-to-inchi), [InChI to SMILES]"
                  "(https://seqandchem.com/inchi-to-smiles) and [SMILES to InChIKey]"
                  "(https://seqandchem.com/smiles-to-inchikey).",
    },
    {
        "slug": "lipinski-rule-of-five",
        "tags": ["chemistry", "science", "opensource", "tutorial"],
        "footer": "Run the rule on any SMILES string with the free "
                  "[drug-likeness checker](https://seqandchem.com/lipinski), or paste a whole "
                  "library into the [batch converter](https://seqandchem.com/batch).",
    },
    {
        "slug": "fasta-vs-fastq",
        "tags": ["bioinformatics", "genomics", "science", "opensource"],
        "footer": "Convert in either direction with [FASTA to FASTQ]"
                  "(https://seqandchem.com/bio/fasta-to-fastq) or [FASTQ to FASTA]"
                  "(https://seqandchem.com/bio/fastq-to-fasta), and get sequence statistics from "
                  "the [GC content calculator](https://seqandchem.com/bio/gc-content).",
    },
]


def to_markdown(html):
    text = md(html, heading_style="ATX", bullets="-", code_language="")
    text = re.sub(r"\]\((/[^)]*)\)", lambda m: "](" + BASE + m.group(1) + ")", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build(spec):
    guide = GUIDES[spec["slug"]]
    body = to_markdown(guide["prose"])
    body += f"\n\n---\n\n*{spec['footer']}*"
    return {
        "title": guide["title"],
        "published": True,
        "body_markdown": body,
        "description": guide["description"][:140],
        "canonical_url": BASE + guide["path"],
        "tags": spec["tags"],
    }


def post(article):
    data = json.dumps({"article": article}).encode()
    req = urllib.request.Request("https://dev.to/api/articles", data=data, method="POST")
    req.add_header("api-key", TOKEN)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "seqchem-crosspost/0.1 (+https://seqandchem.com)")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300].decode("utf-8", "replace")}


if __name__ == "__main__":
    publish = "--publish" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    for spec in ARTICLES:
        if only and spec["slug"] != only:
            continue
        art = build(spec)
        print(f"\n== {art['title']}  ({len(art['body_markdown'])} chars, tags {art['tags']})")
        print(f"   canonical: {art['canonical_url']}")
        if not publish:
            print(art["body_markdown"][:400].replace("\n", "\n   "))
            continue
        status, resp = post(art)
        if status == 201:
            print(f"   published: {resp.get('url')}")
        else:
            print(f"   failed {status}: {str(resp)[:300]}")
