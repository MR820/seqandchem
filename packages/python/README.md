# seqchem

Python client for the free **[SeqChem](https://seqandchem.com)** chemistry and bioinformatics
API — convert between 190+ chemical formats, compute molecular descriptors, draw structures,
generate 3D conformers, search substructures and process FASTA/FASTQ sequences.

No API key, no account, no dependencies (standard library only).

```bash
pip install seqchem
```

## Quick start

```python
from seqchem import Client

c = Client()

# SMILES -> InChI
print(c.convert("CC(=O)Oc1ccccc1C(=O)O", to="inchi")["result"])

# Descriptors (MW, logP, TPSA, HBD, HBA, rotatable bonds, InChIKey, ...)
props = c.properties("CC(=O)Oc1ccccc1C(=O)O")[0]["props"]
print(props["MW"], props["logP"], props["InChIKey"])

# Long batch jobs: bypass the CDN's 100-second timeout
# c = Client(base_url="https://api.seqandchem.com")

# 2D structure as SVG, ready to embed in a notebook or a web page
svg = c.depict("CC(=O)Oc1ccccc1C(=O)O")

# 3D conformer as an SDF block
sdf = c.gen3d("CC(=O)Oc1ccccc1C(=O)O")

# Tanimoto similarity
print(c.similarity("CCO", "CCCO", fp="MACCS"))

# IUPAC name -> structure
print(c.iupac("2-acetoxybenzoic acid")["smiles"])

# FASTA/FASTQ: fasta2fastq, fastq2fasta, revcomp, translate, stats
print(c.bio("revcomp", "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG")["result"])
```

## Command line

The package installs a `seqchem` command:

```bash
seqchem convert "CC(=O)Oc1ccccc1C(=O)O" --to inchi
seqchem properties "CCO" --json
seqchem depict "CCO" > ethanol.svg
seqchem similarity CCO CCCO
seqchem bio revcomp ATGGCC
seqchem formula C9H8O4
cat molecules.sdf | seqchem convert - --from sdf --to smiles
```

## Errors

Everything raises `SeqChemError`, which carries the HTTP status and any detail the service sent:

```python
from seqchem import Client, SeqChemError

try:
    Client().convert("not a molecule", to="inchi")
except SeqChemError as exc:
    print(exc.status, exc.message)
```

`429` means either the fair-use rate limit (120 requests/minute per client) or that a heavy job
is already running — 3D generation is serialised across the whole service.

## Limits

| | |
|---|---|
| Input size | 8 MB per request, 64 MB for `batch()` |
| Batch records | 5,000, or 500 when the output is an image |
| Rate limit | 120 requests/minute per client |

## Links

- **Website**: <https://seqandchem.com>
- **API reference**: <https://seqandchem.com/api>
- **OpenAPI spec**: <https://seqandchem.com/api/openapi.json>
- **Source**: <https://github.com/MR820/seqandchem>

Licensed under Apache-2.0.
