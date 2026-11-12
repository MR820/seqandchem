"""Command line interface: ``seqchem convert CCO --to inchi``."""
from __future__ import annotations

import argparse
import json
import sys

from .client import Client, SeqChemError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="seqchem",
        description="Free chemistry and bioinformatics tools — https://seqandchem.com",
    )
    parser.add_argument("--base-url", default=None, help="use a different SeqChem instance")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("convert", help="convert between chemical formats")
    p.add_argument("data", help="molecule data, or - for stdin")
    p.add_argument("--to", default="mol")
    p.add_argument("--from", dest="frm", default="smi")

    p = sub.add_parser("properties", help="molecular descriptors")
    p.add_argument("data", nargs="?", default="-")
    p.add_argument("--from", dest="frm", default="smi")
    p.add_argument("--json", action="store_true", help="print raw JSON")

    p = sub.add_parser("depict", help="2D structure as SVG")
    p.add_argument("data", nargs="?", default="-")
    p.add_argument("--from", dest="frm", default="smi")

    p = sub.add_parser("similarity", help="Tanimoto similarity of two molecules")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--fp", default="FP2")

    p = sub.add_parser("iupac", help="IUPAC name to SMILES/InChI")
    p.add_argument("name")

    p = sub.add_parser("formula", help="molecular weight from a formula")
    p.add_argument("formula")

    p = sub.add_parser("bio", help="FASTA/FASTQ operations")
    p.add_argument("op", choices=["fasta2fastq", "fastq2fasta", "revcomp", "translate", "stats"])
    p.add_argument("data", nargs="?", default="-")

    args = parser.parse_args(argv)
    client = Client(**({"base_url": args.base_url} if args.base_url else {}))

    def read(data: str) -> str:
        return sys.stdin.read() if data == "-" else data

    try:
        if args.command == "convert":
            print(client.convert(read(args.data), to=args.to, frm=args.frm).get("result", ""))
        elif args.command == "properties":
            rows = client.properties(read(args.data), frm=args.frm)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for row in rows:
                    print(row["smiles"])
                    for key, value in row["props"].items():
                        print(f"  {key:<10} {value}")
        elif args.command == "depict":
            print(client.depict(read(args.data), frm=args.frm))
        elif args.command == "similarity":
            print(f"{client.similarity(args.a, args.b, fp=args.fp):.4f}")
        elif args.command == "iupac":
            result = client.iupac(args.name)
            if result.get("resolved"):
                print(result["smiles"])
            else:
                print(result.get("message", "could not resolve"), file=sys.stderr)
                return 1
        elif args.command == "formula":
            result = client.formula(args.formula)
            print(f"{result['formula']}  {result['mw']:.3f} g/mol")
        elif args.command == "bio":
            result = client.bio(args.op, read(args.data))
            print(json.dumps(result.get("rows", result.get("result")), indent=2))
    except SeqChemError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
