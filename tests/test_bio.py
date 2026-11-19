import pytest

from bio import (
    SequenceError,
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


def test_fastq_rejects_quality_shorter_than_sequence():
    text = "@read1\nATGC\n+\nII\n"
    with pytest.raises(SequenceError) as caught:
        fastq_to_fasta(text)
    assert str(caught.value) == "Invalid FASTQ: sequence and quality lengths differ"
    assert "sequence length 4, quality length 2" in caught.value.detail


def test_fastq_accepts_matching_quality_and_multiple_records():
    text = "@read1\nATGC\n+\nIIII\n\n@read2 desc\nTTAA\n+read2 desc\nIIII\n"
    assert parse_fastq(text) == [
        ("read1", "ATGC", "IIII"),
        ("read2 desc", "TTAA", "IIII"),
    ]
    assert fastq_to_fasta(text) == ">read1\nATGC\n>read2 desc\nTTAA"


def test_fastq_blank_lines_and_special_quality_with_several_records():
    text = (
        "@read1\nGATTACA\n+\n!''*(((\n"
        "\n\n"
        "@read2 desc\nACGT\n+read2 desc\n+@5I\n"
    )
    assert fastq_to_fasta(text) == ">read1\nGATTACA\n>read2 desc\nACGT"
    with pytest.raises(SequenceError) as caught:
        parse_fastq("@read1\nGATTACA\n\n+\n!''*(((\n")
    assert "separator line must start with +" in str(caught.value)


def test_fastq_public_example_and_phred_punctuation():
    seq = "ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"
    qual = "I" * len(seq)
    text = f"@read1\n{seq}\n+\n{qual}"
    assert fastq_to_fasta(text) == f">read1\n{seq}"
    # '+', '@' and digits are legal quality characters and must not be read as structure.
    assert fastq_to_fasta("@r\nACGT\n+\n+@I~\n") == ">r\nACGT"
    assert fastq_to_fasta("@r\nAC\n+\n5I\n") == ">r\nAC"
    assert fastq_to_fasta("@r\nATGN\n+\nIIII\n") == ">r\nATGN"
    assert fastq_to_fasta("@r\r\nAC\r\n+\r\nII\r\n") == ">r\nAC"


def test_fastq_middle_truncated_and_wrapped_records_fail():
    middle = "@ok\nATGC\n+\nIIII\n@bad\nATGC\n+\nII\n@later\nGG\n+\nII\n"
    with pytest.raises(SequenceError) as caught:
        parse_fastq(middle)
    assert "Record 2 (bad)" in caught.value.detail

    with pytest.raises(SequenceError) as caught:
        parse_fastq("@ok\nATGC\n+\nIIII\n@tail\nATGC\n")
    assert str(caught.value) == "Invalid FASTQ: truncated record"

    with pytest.raises(SequenceError):
        parse_fastq("@read\nATGC\nATGC\n+\nIIIIIIII\n")

    with pytest.raises(SequenceError) as caught:
        parse_fastq("@r\nAC\n+\n I\n")
    assert str(caught.value) == (
        "Invalid FASTQ: quality characters are outside the Phred range"
    )


def test_reverse_complement_iupac_rna_and_layout():
    assert reverse_complement("ATGCRY") == "RYGCAT"
    assert reverse_complement("AUGC") == "GCAT"
    assert reverse_complement("augc") == "gcat"
    assert reverse_complement("ATGC\nRY") == "RYGCAT"
    assert reverse_complement("AT GC") == "GCAT"
    assert reverse_complement(">s\nAT GC") == ">s\nGCAT"
    src = "ACGTUNRYKMSWBDHV"
    dst = "TGCAANYRMKSWVHDB"
    assert reverse_complement(src) == dst[::-1]
    assert reverse_complement(src.lower()) == dst.lower()[::-1]
    assert reverse_complement(">read1\nATGC") == ">read1\nGCAT"
    assert reverse_complement(">a\nAT\nGC\n>b\nAU\n") == ">a\nGCAT\n>b\nAT"
    assert reverse_complement(">s\n" + ("A" * 71)) == ">s\n" + ("T" * 70) + "\nT"
    assert "\n" not in reverse_complement("A" * 80)


def test_reverse_complement_rejects_non_nucleotides():
    with pytest.raises(SequenceError) as caught:
        reverse_complement("12345")
    assert str(caught.value) == (
        "Invalid sequence: characters are not DNA, RNA or IUPAC ambiguity codes"
    )
    assert "'1'" in caught.value.detail
    with pytest.raises(SequenceError) as caught:
        reverse_complement(">ok\nATGC\n>bad\n12\n")
    assert "Record bad" in caught.value.detail
    assert "GCAT" not in str(caught.value)
