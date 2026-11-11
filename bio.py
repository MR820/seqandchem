"""FASTA / FASTQ 序列工具（纯 Python 实现，无需 Biopython）"""
import re

DNA_COMPLEMENT = str.maketrans("ACGTUNRYKMSWBDHVacgtunrykmswbdhv",
                               "TGCAANYRMKSWVHDBtgcaanyrmkswvhdb")

CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def parse_fasta(text):
    """返回 [(header, sequence)]"""
    records, header, seq = [], None, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(seq)))
            header, seq = line[1:], []
        else:
            seq.append(line)
    if header is not None:
        records.append((header, "".join(seq)))
    return records


def parse_fastq(text):
    """返回 [(header, sequence, quality)]"""
    lines = [l.rstrip("\n") for l in text.splitlines() if l.strip()]
    records = []
    i = 0
    while i + 3 < len(lines):
        head, seq, plus, qual = lines[i], lines[i + 1], lines[i + 2], lines[i + 3]
        if head.startswith("@"):
            records.append((head[1:], seq, qual))
            i += 4
        else:
            i += 1
    return records


def wrap(seq, width=70):
    return "\n".join(seq[i:i + width] for i in range(0, len(seq), width))


def fasta_to_fastq(text, quality="I"):
    out = []
    for header, seq in parse_fasta(text):
        qual = quality * len(seq)
        out.append(f"@{header}\n{seq}\n+\n{qual}")
    return "\n".join(out)


def fastq_to_fasta(text):
    out = []
    for header, seq, _ in parse_fastq(text):
        out.append(f">{header}\n{wrap(seq)}")
    return "\n".join(out)


def reverse_complement(text):
    """支持 FASTA 输入或裸序列"""
    if text.lstrip().startswith(">"):
        out = []
        for header, seq in parse_fasta(text):
            out.append(f">{header}\n{wrap(seq.translate(DNA_COMPLEMENT)[::-1])}")
        return "\n".join(out)
    return text.translate(DNA_COMPLEMENT)[::-1].strip()


def translate(text, frame=0):
    """翻译 CDS；输出单字母氨基酸序列"""
    def _tr(seq):
        seq = seq.upper().replace("U", "T")
        start = frame
        aa = []
        for i in range(start, len(seq) - 2, 3):
            aa.append(CODON_TABLE.get(seq[i:i + 3], "X"))
        return "".join(aa)

    if text.lstrip().startswith(">"):
        out = []
        for header, seq in parse_fasta(text):
            out.append(f">{header}\n{_tr(seq)}")
        return "\n".join(out)
    return _tr(text)


def sequence_stats(text):
    """返回每个序列的统计信息"""
    records = parse_fasta(text) if text.lstrip().startswith(">") else [("sequence", text.replace("\n", "").strip())]
    rows = []
    for header, seq in records:
        s = seq.upper()
        n = len(s)
        gc = s.count("G") + s.count("C")
        at = s.count("A") + s.count("T") + s.count("U")
        amb = sum(s.count(c) for c in "NRYKMSWBDHV")
        rows.append({
            "header": header,
            "length": n,
            "gc": gc,
            "gc_pct": round(gc / n * 100, 2) if n else 0.0,
            "at_pct": round(at / n * 100, 2) if n else 0.0,
            "n_count": s.count("N"),
            "ambiguous": amb,
            "gc_skew": round((s.count("G") - s.count("C")) / (s.count("G") + s.count("C")), 3)
            if (s.count("G") + s.count("C")) else 0.0,
            "at_skew": round((s.count("A") - s.count("T")) / (s.count("A") + s.count("T")), 3)
            if (s.count("A") + s.count("T")) else 0.0,
        })
    return rows
