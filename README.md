# SeqChem

**Free online chemistry and bioinformatics tools — <https://seqandchem.com>**

SeqChem is a small, dependency-light web application that puts OpenBabel, OPSIN and a set of native
sequence utilities behind a plain HTML interface and a public JSON API. No account, no paywall, no
usage metering.

- Website: **<https://seqandchem.com>**
- API documentation: **<https://seqandchem.com/api>**
- OpenAPI spec: **<https://seqandchem.com/api/openapi.json>**

---

## What it does

### Chemical formats
Convert between 190+ formats supported by OpenBabel — SMILES, InChI, InChIKey, MOL, SDF, MOL2,
PDB, XYZ, CML, PNG, SVG and many more. There are 26 dedicated one-click converter pages plus a
generic converter, and a batch endpoint for whole libraries.

| Tool | URL |
|---|---|
| Format converter | `/convert` |
| Batch converter | `/batch` |
| SMILES → InChI | `/smiles-to-inchi` |
| InChI → SMILES | `/inchi-to-smiles` |
| SDF → SMILES | `/sdf-to-smiles` |
| SMILES → MOL / MOL2 / XYZ / SDF / CML | `/smiles-to-*` |
| PDB → SMILES / SDF / InChI | `/pdb-to-*` |

### Structure analysis
- **Descriptors** — formula, MW, logP, TPSA, HBD, HBA, rotatable bonds, molar refractivity, InChI, InChIKey (`/properties`)
- **2D depiction** — SVG structure rendering (`/depict`)
- **3D conformer** — force-field optimisation, rendered in-browser with 3Dmol.js (`/3d`)
- **Substructure search** — SMARTS filtering (`/substructure`)
- **Similarity** — Tanimoto over FP2/FP3/FP4/MACCS (`/similarity`)
- **Drug-likeness** — Lipinski rule of five plus Veber criteria (`/lipinski`)
- **IUPAC name → structure** — OPSIN with a PubChem fallback (`/iupac-to-structure`)
- **Formula ↔ structure** (`/formula`)

### Sequence tools
Pure-Python FASTA/FASTQ utilities — no external services, no data leaves the server:

- FASTA → FASTQ and FASTQ → FASTA (`/bio/fasta-to-fastq`, `/bio/fastq-to-fasta`)
- GC content and sequence statistics (`/bio/gc-content`)
- Reverse complement with IUPAC ambiguity codes (`/bio/reverse-complement`)
- DNA → protein translation in all frames (`/bio/translate`)

### Guides
Long-form explainers that back the tools: SMILES vs InChI vs InChIKey, Lipinski's rule of five,
FASTA vs FASTQ (`/guides/`).

---

## API

No API key. JSON in, JSON out. CORS enabled. Fair use: 120 requests/minute per client,
300/minute across the service; 8 MB maximum input per request.

```bash
curl -s https://seqandchem.com/api/v1/properties \
  -H 'Content-Type: application/json' \
  -d '{"from":"smi","data":"CC(=O)Oc1ccccc1C(=O)O"}'
```

Endpoints: `/api/v1/formats`, `/api/v1/example`, `/api/v1/convert`, `/api/v1/properties`,
`/api/v1/depict`, `/api/v1/gen3d`, `/api/v1/substructure`, `/api/v1/fingerprint`,
`/api/v1/similarity`, `/api/v1/iupac`, `/api/v1/batch`, `/api/v1/formula`, `/api/v1/bio`.

Full reference with request/response examples: <https://seqandchem.com/api>

---

## Stack

- **Flask 3** + **gunicorn**, served behind nginx
- **OpenBabel 3.1.1** CLI for all molecule work (invoked as a subprocess)
- **OPSIN** (University of Cambridge) for IUPAC name parsing, over HTTP
- **3Dmol.js** for client-side 3D rendering
- **GoatCounter** for privacy-friendly page analytics
- No database — the app is stateless

## Repository layout

```
app.py            Flask app: routes, public API, rate limiting, SEO metadata
presets.py        Data for the 20 long-tail converter pages (unique copy per page)
guides.py         Long-form guide articles
bio.py            FASTA/FASTQ parsing and sequence operations
formula.py        Molecular formula parsing and weight calculation
templates/        Jinja2 templates (base layout, one per tool, docs, guides)
static/           CSS, app.js, 3Dmol bundle, favicon
deploy/           systemd unit, nginx vhost, monitoring script
```

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# plus the OpenBabel CLI, which is a system package:
#   Debian/Ubuntu: apt install openbabel
#   macOS:         brew install open-babel
BASE_URL=http://127.0.0.1:8080 python app.py
```

The app serves on `127.0.0.1:8080`; open <http://127.0.0.1:8080>.

## Deploying

`deploy/chemtools.service` and `deploy/nginx.conf` are the production configuration used at
<https://seqandchem.com>: gunicorn on `127.0.0.1:8080` under a dedicated `chemtools` user, with
nginx terminating TLS.

`deploy/daily-report.sh` is the operations health check that pushes a daily summary (traffic,
crawler coverage, service state, security updates) to a Feishu bot.

## Privacy

Nothing is stored server-side. Molecules and sequences are converted in a subprocess and discarded.
The only analytics is GoatCounter — cookie-free, no personal data, no cross-site tracking.

## Credits

- **OpenBabel** — GPL-2.0, the chemistry engine behind every conversion and descriptor. Used as an
  external command-line dependency; it is not vendored into this repository.
- **OPSIN** — University of Cambridge, IUPAC name parsing, called over HTTP
- **3Dmol.js** — BSD-3-Clause, in-browser 3D rendering. Bundled at `static/3dmol-min.js` and
  remains under its own BSD-3-Clause licence.
- **PubChem PUG REST** — fallback for trivial names and structure lookup

## Licence

Apache License 2.0 — see [LICENSE](LICENSE). This covers this repository's own source code;
third-party components keep their original licences as noted above.
