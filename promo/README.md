# Promotion

## awesome-list submissions

Four pull requests, each adding one line to a curated list that already covers comparable tools.
Patches are in `promo/awesome-lists/`; each is a single-line insertion in the right section.

| Repository | ★ | Section | Entry |
|---|---|---|---|
| [brandonhimpfen/awesome-chemistry](https://github.com/brandonhimpfen/awesome-chemistry) | 23 | Cheminformatics & Molecular Modeling | SeqChem — converter + descriptors |
| [yboulaamane/awesome-drug-discovery](https://github.com/yboulaamane/awesome-drug-discovery) | 159 | Molecular Property Prediction | SeqChem — property calculator |
| [hsiaoyi0504/awesome-cheminformatics](https://github.com/hsiaoyi0504/awesome-cheminformatics) | 896 | Web APIs | SeqChem API — REST + OpenAPI |
| [danielecook/Awesome-Bioinformatics](https://github.com/danielecook/Awesome-Bioinformatics) | 4361 | Sequence Processing | SeqChem — FASTA/FASTQ web tools |

Each list was checked first: the entry matches that section's existing formatting (`-` vs `*`,
en dash vs hyphen, bold names) and sits next to entries of the same kind (other web tools or
REST APIs). Nothing was added to a list that does not already cover this category.

### Applying by hand

1. Fork the repository on GitHub.
2. Open `README.md` in the fork, press **Edit**.
3. Apply the matching `.patch` by hand — it is one inserted line.
4. Commit to a new branch, e.g. `add-seqchem`.
5. Open a pull request using the body in `promo/pr-bodies/<repo>.md`.

### Applying with the API

`promo/open_prs.py` does the fork → commit → PR sequence for all four in one run:

```bash
python3 promo/open_prs.py --dry-run   # preview the diff for each list
python3 promo/open_prs.py --apply     # fork, commit, open the PRs
```

It reads a token from `~/.config/seqchem/github_token` and needs the `public_repo` scope.
Nothing else is touched.

## Other channels

- **PyPI package** — a `seqchem` Python client (needs a PyPI token) gives a project page that links
  back here and is genuinely installable.
- **Embeddable widget** — `/embed` is live; a one-line iframe gives site owners a reason to link
  without anyone asking them to.
- **llms.txt** — `/llms.txt` is live for agent tooling and LLM crawlers.

## What we do not do

No comment spam, no forum signature links, no paid link networks, no auto-generated directory
listings. Those produce links that search engines discount and can actively penalise.
