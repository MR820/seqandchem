from bio import (
    fasta_to_fastq,
    fastq_to_fasta,
    parse_fasta,
    parse_fastq,
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
