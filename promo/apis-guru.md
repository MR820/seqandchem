# APIs.guru submission — SeqChem

Status checked 2026-11-13: `seqandchem` / `seqchem` is **not in the collection**.

APIs.guru does **not** accept pull requests that add or edit `openapi.yaml` files; use the Add API
web form instead (see `CONTRIBUTING.md` in `API-guru/openapi-directory`):

**Submit here: <https://apis.guru/add-api/>**

## Form values

| Field | Value |
|---|---|
| API Definition URL | `https://seqandchem.com/api/openapi.json` |
| Format of the definition | **OpenAPI/Swagger** |
| Is the definition official? | **Yes, by API owner** |
| API Name | `SeqChem` |
| API Logo URL | `https://seqandchem.com/favicon.svg` (square SVG; a 512×512 PNG is acceptable if preferred) |
| Category | **Tools** (`tools`) |

There is no contact field in the form. If a follow-up email is needed, use the GitHub issue
tracker: <https://github.com/MR820/seqandchem/issues>.

## Short description (if asked)

> Free public JSON API for chemistry and bioinformatics: 190+ format conversions (SMILES, InChI,
> MOL, SDF, PDB, MOL2, XYZ, CML), molecular descriptors, 2D/3D depiction, SMARTS substructure
> search, Tanimoto similarity, IUPAC name resolution, batch conversion and FASTA/FASTQ tools.
> No API key, CORS enabled, OpenAPI 3.0.3.

## Pre-submit checks

```bash
# Spec is valid JSON and published
curl -s https://seqandchem.com/api/openapi.json | python3 -m json.tool >/dev/null && echo OK

# API is reachable without auth
curl -s -o /dev/null -w '%{http_code}\n' https://seqandchem.com/api/v1/formats
```

Current API facts:

- OpenAPI `3.0.3`
- 13 endpoints under `/api/v1/*`
- No authentication
- CORS enabled (`access-control-allow-origin: *`)
- Fair use: 120 requests/min per client, 300/min total; 8 MB input, 64 MB batch
- Long batch jobs can use the DNS-only `https://api.seqandchem.com` endpoint

## After submission

APIs.guru updates definitions weekly. Check:

- <https://apis.guru/?search=seqchem>
- <https://api.apis.guru/v2/list.json> (search for `seqandchem.com`)

If they ask for a category change, `data` or `education` are the closest alternatives; `tools`
is the best fit for a utility API.
