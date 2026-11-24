import pytest

from bio import (
    dna_molecular_weight,
    fasta_to_fastq,
    fastq_to_fasta,
    parse_fasta,
    parse_fastq,
    primer_tm,
    protein_molecular_weight,
    reverse_complement,
    sequence_stats,
    translate,
)


def test_parse_fasta_multiple_records():
    records = parse_fasta(">a\nACGT\n>b\nTTAA\n")
    assert records == [("a", "ACGT"), ("b", "TTAA")]


def test_fasta_fastq_round_trip():
    fasta = ">read1\nACGT\n>read2\nTT\n"
    fastq = fasta_to_fastq(fasta, quality="I")
    assert fastq.startswith("@read1\nACGT\n+\nIIII")
    assert parse_fastq(fastq) == [("read1", "ACGT", "IIII"), ("read2", "TT", "II")]
    assert fastq_to_fasta(fastq) == ">read1\nACGT\n>read2\nTT"


def test_reverse_complement_and_iupac_codes():
    assert reverse_complement("ATGC") == "GCAT"
    assert reverse_complement("ACGTN") == "NACGT"
    assert ">seq" in reverse_complement(">seq\nATGC")


def test_translation_frames():
    assert translate("ATGTTT") == "MF"
    assert translate("ATGTTT", frame=1) == "C"
    assert translate(">s\nATGTTT").startswith(">s\n")


def test_sequence_stats():
    row = sequence_stats("ATGC")[0]
    assert row["length"] == 4
    assert row["gc"] == 2
    assert row["gc_pct"] == 50.0


def test_protein_molecular_weight():
    row = protein_molecular_weight("DRVYIHPF")[0]
    assert row["length"] == 8
    assert row["residues"] == 8
    assert abs(row["mw"] - 1046.19) < 0.1
    assert abs(row["mono"] - 1045.54) < 0.1


def test_protein_molecular_weight_unknown_codes():
    row = protein_molecular_weight("DRVYX")[0]
    assert row["unknown"] == 1
    assert row["unknown_codes"] == "X"


def test_dna_molecular_weight():
    row = dna_molecular_weight("ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG")[0]
    assert row["type"] == "DNA"
    assert row["length"] == 39
    assert row["gc_pct"] == 56.41
    assert abs(row["ss_mw"] - 12192.89) < 0.1
    assert abs(row["ds_mw"] - 2 * row["ss_mw"]) < 0.01


def test_rna_molecular_weight_and_mixed_rejection():
    row = dna_molecular_weight("AUGGCCAUUGUAAUGGGCCGCUGAAAGGGUGCCCGAUAG")[0]
    assert row["type"] == "RNA"
    assert "U" in row["counts"]
    with pytest.raises(ValueError):
        dna_molecular_weight("ATUG")


def test_primer_tm():
    row = primer_tm("ATGGCCATTGTAATGGGCCG")[0]
    assert row["length"] == 20
    assert row["gc_pct"] == 55.0
    assert row["wallace"] == 62.0
    assert row["tm_salt"] == 52.5
    assert row["gc3"] == 5
    assert row["warnings"] == []


def test_primer_tm_short_and_ambiguous():
    row = primer_tm("ACGT")[0]
    assert row["tm_salt"] is None
    assert any("Shorter than 14" in w for w in row["warnings"])
    row = primer_tm("ATGGCCATTGTAATGGGCCN")[0]
    assert row["unknown"] == 1
    assert any("ignored" in w for w in row["warnings"])
