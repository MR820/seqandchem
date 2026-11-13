# bio.tools submission — SeqChem

Status checked 2026-11-13: `seqchem` is **not listed**, and the ID `seqchem` is available
(`GET https://bio.tools/api/t/seqchem` → 404).

- Sign up: <https://bio.tools/signup>
- Add content: <https://bio.tools/register>
- Curator guide: <https://biotools.readthedocs.io/en/latest/curators_guide.html>

## Basic fields

| Field | Value |
|---|---|
| Name | SeqChem |
| bio.tools ID | `seqchem` |
| Description | Free web application and JSON API for chemistry and bioinformatics. Converts 190+ chemical formats (SMILES, InChI, MOL, SDF, PDB, MOL2, XYZ, CML), calculates molecular properties, draws 2D structures, generates 3D conformers, runs SMARTS substructure and Tanimoto similarity searches, resolves IUPAC names, and processes FASTA/FASTQ sequences. No account, no API key, open source. |
| Homepage | <https://seqandchem.com> |
| Version | `1.0.0` |
| Tool type | Web application; Web service |
| Operating system | Linux |
| Language | Python; JavaScript |
| License | Apache-2.0 |
| Cost | Free of charge |
| Accessibility | Open access |
| Maturity | Emerging |
| Contact | Use the GitHub issue tracker: <https://github.com/MR820/seqandchem/issues> |

## Topics

| EDAM URI | Term |
|---|---|
| <http://edamontology.org/topic_0091> | Bioinformatics |
| <http://edamontology.org/topic_2258> | Cheminformatics |
| <http://edamontology.org/topic_0080> | Sequence analysis |
| <http://edamontology.org/topic_0092> | Data visualisation |

## Documentation

| URL | Type | Note |
|---|---|---|
| <https://seqandchem.com/api> | API documentation | JSON API reference and OpenAPI 3.0 spec |
| <https://seqandchem.com/api/openapi.json> | API documentation | Machine-readable OpenAPI definition |
| <https://github.com/MR820/seqandchem> | General | Source code, README and deployment notes |

## Links

| URL | Type | Note |
|---|---|---|
| <https://seqandchem.com> | Service | Hosted web application |
| <https://github.com/MR820/seqandchem> | Repository | Source code |
| <https://pypi.org/project/seqchem/> | Package distribution | Python client |
| <https://github.com/MR820/seqandchem/issues> | Issue tracker | Bug reports and feature requests |

## Functions

### 1. Chemical format conversion
- **Operations:** Data formatting (`operation_0335`)
- **Input:** Small molecule structure (`data_1463`) — SMILES (`format_1196`), InChI (`format_1197`), Molfile (`format_3815`), SDF (`format_3814`), PDB (`format_1476`), Mol2 (`format_3816`), XYZ (`format_3877`), CML (`format_4023`)
- **Output:** Small molecule structure (`data_1463`) — same formats plus InChIKey (`format_1199`)

### 2. Molecular property calculation
- **Operations:** Calculation (`operation_3438`)
- **Input:** Small molecule structure (`data_1463`) — SMILES, InChI, SDF
- **Output:** Molecular property (general) (`data_2050`)

### 3. 2D and 3D structure visualisation
- **Operations:** Structure visualisation (`operation_0570`), Visualisation (`operation_0337`)
- **Input:** Small molecule structure (`data_1463`) — SMILES, InChI
- **Output:** Chemical structure image (`data_1712`) — SVG (`format_3604`), PNG (`format_3603`); Small molecule structure (`data_1463`) — SDF, Molfile (3D conformer)

### 4. Substructure and similarity search
- **Operations:** Structure database search (`operation_0339`), Structural similarity search (`operation_0360`)
- **Input:** Small molecule structure (`data_1463`) — SMILES, InChI, SDF; Query script (`data_3786`) — smarts (`format_1200`)
- **Output:** Small molecule structure (`data_1463`) — SMILES, SDF

### 5. FASTA/FASTQ sequence tools
- **Operations:** Sequence analysis (`operation_2403`), DNA translation (`operation_0371`), Nucleic acid property calculation (`operation_0262`)
- **Input:** DNA sequence (`data_3494`) — FASTA (`format_1929`), FASTQ (`format_1930`); RNA sequence (`data_3495`) — FASTA
- **Output:** Protein sequence (`data_2976`); Sequence property (`data_1254`)

### 6. IUPAC name to structure
- **Operations:** Data formatting (`operation_0335`), Calculation (`operation_3438`)
- **Input:** Chemical name (IUPAC) (`data_0998`)
- **Output:** Small molecule structure (`data_1463`) — SMILES, InChI, InChIKey; Chemical structure image (`data_1712`) — SVG

## Fill-in note

The UI has ~10 tabs. Minimum required fields are name, description and homepage; fill the
function tab with the six entries above. If a field rejects a value, the likely alternative is:

- Tool type: `Web application` (instead of `Web service`)
- Operating system: leave empty for a hosted web tool
- Maturity: `Emerging` or `Mature`
- Cost / accessibility: `Free of charge` / `Open access`

A JSON draft is in [`bio-tools.json`](bio-tools.json) for reference.
