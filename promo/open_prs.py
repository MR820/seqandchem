#!/usr/bin/env python3
"""Open one pull request per curated list in promo/awesome-lists/.

    python3 promo/open_prs.py --dry-run    # preview every diff, no writes
    python3 promo/open_prs.py --apply      # fork, commit, open the PRs

Needs a GitHub token with the `public_repo` scope at
~/.config/seqchem/github_token (chmod 600).
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
USER = "MR820"
BRANCH = "add-seqchem"
GH_USER = "MR820"

TARGETS = [
    {
        "repo": "brandonhimpfen/awesome-chemistry",
        "heading": "## Cheminformatics & Molecular Modeling",
        "entry": "- [SeqChem](https://seqandchem.com/) – Free browser-based converter and descriptor "
                 "calculator for 190+ chemical formats, with SMILES/InChI support and a public JSON API.",
        "title": "Add SeqChem (free browser-based chemistry tools)",
    },
    {
        "repo": "yboulaamane/awesome-drug-discovery",
        "heading": "### Molecular Property Prediction",
        "entry": "- [SeqChem](https://seqandchem.com/properties) - Free web calculator for molecular "
                 "weight, logP, TPSA, H-bond donors/acceptors, rotatable bonds and Lipinski/Veber rule "
                 "checks, with batch mode for whole libraries.",
        "title": "Add SeqChem property calculator to Molecular Property Prediction",
    },
    {
        "repo": "hsiaoyi0504/awesome-cheminformatics",
        "heading": "### Web APIs",
        "entry": "* [SeqChem API](https://seqandchem.com/api) - Free REST API for chemical format "
                 "conversion, molecular descriptors, 2D depiction and 3D conformer generation. "
                 "[OpenAPI spec](https://seqandchem.com/api/openapi.json)",
        "title": "Add SeqChem REST API to Web APIs",
    },
    {
        "repo": "danielecook/Awesome-Bioinformatics",
        "heading": "### Sequence Processing",
        "entry": "- **[SeqChem](https://seqandchem.com/bio/)** - Web-based FASTA/FASTQ conversion, GC "
                 "content, reverse complement and DNA translation. [ [web](https://seqandchem.com/bio/) ]",
        "title": "Add SeqChem web tools to Sequence Processing",
    },
]


def token():
    p = os.path.expanduser("~/.config/seqchem/github_token")
    if not os.path.exists(p):
        sys.exit(f"No token at {p}")
    return open(p).read().strip()


def call(tok, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "token " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300].decode("utf-8", "replace")}


def insert_entry(text, heading, entry):
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        raise SystemExit(f"heading not found: {heading!r}")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^(#{2,3} |<a id=)", lines[i]):
            end = i
            break
    body = lines[start + 1:end]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(lines[:start + 1] + body + [entry, ""] + lines[end:])


def body_for(repo):
    slug = repo.replace("/", "__")
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pr-bodies", slug + ".md")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def process(tok, t, dry):
    repo = t["repo"]
    name = repo.split("/")[1]

    st, info = call(tok, "GET", f"/repos/{repo}")
    if st != 200:
        print(f"  ! cannot read {repo}: {st}")
        return False
    base = info["default_branch"]

    if dry:
        st, rd = call(tok, "GET", f"/repos/{repo}/contents/README.md?ref={base}")
        if st != 200:
            print(f"  ! README missing: {st}")
            return False
        original = base64.b64decode(rd["content"]).decode("utf-8")
        updated = insert_entry(original, t["heading"], t["entry"])
        lines = updated.split("\n")
        idx = next(i for i, l in enumerate(lines) if l.strip() == t["heading"])
        print("  preview:")
        for line in lines[idx:idx + 12]:
            print("   ", line[:110])
        return True

    st, _ = call(tok, "GET", f"/repos/{GH_USER}/{name}")
    if st != 200:
        print(f"  forking {repo} …")
        call(tok, "POST", f"/repos/{repo}/forks", {})
        for _ in range(30):
            time.sleep(2)
            st, _ = call(tok, "GET", f"/repos/{GH_USER}/{name}")
            if st == 200:
                break
        if st != 200:
            print("  ! fork never appeared")
            return False

    # The contents API does not create a branch for you: point one at the
    # default branch's head first, then commit onto it.
    st, ref = call(tok, "GET", f"/repos/{GH_USER}/{name}/git/ref/heads/{BRANCH}")
    if st != 200:
        st, base_ref = call(tok, "GET", f"/repos/{GH_USER}/{name}/git/ref/heads/{base}")
        if st != 200:
            print(f"  ! cannot read {base}: {st}")
            return False
        st, created = call(tok, "POST", f"/repos/{GH_USER}/{name}/git/refs", {
            "ref": f"refs/heads/{BRANCH}", "sha": base_ref["object"]["sha"],
        })
        if st not in (201, 422):
            print(f"  ! branch create failed: {st} {str(created)[:150]}")
            return False

    st, rd = call(tok, "GET", f"/repos/{GH_USER}/{name}/contents/README.md?ref={BRANCH}")
    if st != 200:
        print(f"  ! README missing: {st}")
        return False
    original = base64.b64decode(rd["content"]).decode("utf-8")
    updated = insert_entry(original, t["heading"], t["entry"])

    if updated == original:
        print("  entry already present, skipping commit")
    else:
        st, put = call(tok, "PUT", f"/repos/{GH_USER}/{name}/contents/README.md", {
            "message": f"Add SeqChem to {t['heading'].lstrip('# ')}",
            "content": base64.b64encode(updated.encode("utf-8")).decode("ascii"),
            "sha": rd["sha"],
            "branch": BRANCH,
        })
        if st not in (200, 201):
            print(f"  ! commit failed: {st} {str(put)[:150]}")
            return False
        print("  committed")

    st, pr = call(tok, "POST", f"/repos/{repo}/pulls", {
        "title": t["title"], "head": f"{GH_USER}:{BRANCH}", "base": base, "body": body_for(repo),
    })
    if st == 201:
        print(f"  PR opened: {pr['html_url']}")
        return True
    if st == 422 and "already exists" in json.dumps(pr):
        print("  PR already open")
        return True
    print(f"  ! PR failed: {st} {str(pr)[:180]}")
    return False


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    print("DRY RUN — nothing is written" if not apply else "APPLYING")
    tok = token()
    for t in TARGETS:
        print(f"\n== {t['repo']}")
        try:
            process(tok, t, not apply)
        except SystemExit as exc:
            print("  !", exc)
        time.sleep(1)
