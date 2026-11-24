"""FASTA / FASTQ 序列工具（纯 Python 实现，无需 Biopython）"""
import math

DNA_COMPLEMENT = str.maketrans("ACGTUNRYKMSWBDHVacgtunrykmswbdhv",
                               "TGCAANYRMKSWVHDBtgcaanyrmkswvhdb")
# DNA / RNA / IUPAC 歧义码。与互补表一一对应；空白只当分隔，不算碱基。
NA_CHARS = frozenset("ACGTUNRYKMSWBDHVacgtunrykmswbdhv")


class SequenceError(ValueError):
    """序列或 FASTQ 未通过校验。message 给用户，detail 定位到记录。"""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.detail = detail


def _unexpected(chars, ok):
    bad, seen = [], set()
    for ch in chars:
        if ok(ch) or ch in seen:
            continue
        seen.add(ch)
        bad.append(ch)
        if len(bad) >= 8:
            break
    return bad


def _show(chars):
    return ", ".join(repr(ch) for ch in chars)


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


def _fastq_name(head):
    name = head[1:].strip() if head.startswith("@") else head.strip()
    if not name:
        return "unnamed"
    return name[:60] + ("..." if len(name) > 60 else "")


def parse_fastq(text):
    """返回 [(header, sequence, quality)]。

    只接受标准四行 FASTQ。记录之间的空行跳过；记录被截断、标题或
    ``+`` 分隔行不对、质量串与序列不等长，或质量字符超出 ASCII 33-126
    （Phred+33 / Phred+64 都能放下的可打印范围）时抛 SequenceError。
    不把多行折行的旧式 FASTQ 当成合法输入。
    """
    lines = text.splitlines()
    records = []
    i, n, seen = 0, len(lines), 0
    while i < n:
        if lines[i].strip() == "":
            i += 1
            continue
        seen += 1
        if i + 3 >= n:
            raise SequenceError(
                "Invalid FASTQ: truncated record",
                f"Record {seen} ({_fastq_name(lines[i])}) is incomplete",
            )
        head, seq, plus, qual = lines[i], lines[i + 1], lines[i + 2], lines[i + 3]
        where = f"Record {seen} ({_fastq_name(head)})"
        if not head.startswith("@"):
            raise SequenceError("Invalid FASTQ: header must start with @", where)
        if not plus.startswith("+"):
            raise SequenceError(
                "Invalid FASTQ: separator line must start with +", where
            )
        if len(seq) != len(qual):
            raise SequenceError(
                "Invalid FASTQ: sequence and quality lengths differ",
                f"{where}: sequence length {len(seq)}, quality length {len(qual)}",
            )
        bad = _unexpected(qual, lambda ch: 33 <= ord(ch) <= 126)
        if bad:
            raise SequenceError(
                "Invalid FASTQ: quality characters are outside the Phred range",
                f"{where}: {_show(bad)} not in ASCII 33-126",
            )
        records.append((head[1:], seq, qual))
        i += 4
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


def _na_bases(seq):
    """空白只作分隔，不参与互补。"""
    return "".join(ch for ch in seq if not ch.isspace())


def _check_na(seq, where):
    bad = _unexpected(seq, lambda ch: ch in NA_CHARS)
    if bad:
        raise SequenceError(
            "Invalid sequence: characters are not DNA, RNA or IUPAC ambiguity codes",
            f"{where}: {_show(bad)}",
        )


def reverse_complement(text):
    """FASTA 按记录反向互补；裸序列整段当作一条。

    允许 A/C/G/T/U（RNA 的 U 互补为 A，A 仍互补为 T）以及 IUPAC
    歧义码 N/R/Y/K/M/S/W/B/D/H/V，大小写都保留。其它字符拒绝。
    空白被忽略：多行裸序列先拼成一条再互补，结果是单行；FASTA
    各记录独立，输出按 70 列折行。
    """
    if text.lstrip().startswith(">"):
        records = parse_fasta(text)
        if not records:
            raise SequenceError(
                "No FASTA records found",
                "Input starts with > but has no records",
            )
        out = []
        for header, seq in records:
            bases = _na_bases(seq)
            label = header.strip() or "unnamed"
            if len(label) > 60:
                label = label[:60] + "..."
            _check_na(bases, f"Record {label}")
            out.append(f">{header}\n{wrap(bases.translate(DNA_COMPLEMENT)[::-1])}")
        return "\n".join(out)
    bases = _na_bases(text)
    _check_na(bases, "Sequence")
    return bases.translate(DNA_COMPLEMENT)[::-1]


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


# ────────────────────────────────────────────── 蛋白/DNA 分子量
WATER_MASS = 18.01528

# Average residue masses in a polypeptide chain (Da). Free amino acid minus H2O.
PROTEIN_RESIDUE_MASSES = {
    "A": 71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886, "C": 103.1388,
    "E": 129.1155, "Q": 128.1307, "G": 57.0519, "H": 137.1411, "I": 113.1594,
    "L": 113.1594, "K": 128.1741, "M": 131.1926, "F": 147.1766, "P": 97.1167,
    "S": 87.0782, "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V": 99.1326,
    "U": 150.0388,  # selenocysteine
    "O": 237.3018,  # pyrrolysine
}

PROTEIN_RESIDUE_MONO = {
    "A": 71.03711, "R": 156.10111, "N": 114.04293, "D": 115.02694, "C": 103.00919,
    "E": 129.04259, "Q": 128.05858, "G": 57.02146, "H": 137.05891, "I": 113.08406,
    "L": 113.08406, "K": 128.09496, "M": 131.04049, "F": 147.06841, "P": 97.05276,
    "S": 87.03203, "T": 101.04768, "W": 186.07931, "Y": 163.06333, "V": 99.06841,
    "U": 150.95364,
    "O": 237.14773,
}

# Average residue masses in a DNA/RNA chain (Da). Free nucleotide minus H2O.
DNA_RESIDUE_MASSES = {"A": 313.21, "T": 304.20, "G": 329.21, "C": 289.18}
RNA_RESIDUE_MASSES = {"A": 329.21, "U": 306.17, "G": 345.21, "C": 305.18}


def _sequence_records(text):
    if text.lstrip().startswith(">"):
        return parse_fasta(text)
    return [("sequence", "".join(text.split()))]


def protein_molecular_weight(text):
    """Average and monoisotopic mass for protein/peptide sequences."""
    rows = []
    for header, seq in _sequence_records(text):
        s = "".join(ch for ch in seq.upper() if ch.isalpha())
        if not s:
            continue
        known = [ch for ch in s if ch in PROTEIN_RESIDUE_MASSES]
        unknown = [ch for ch in s if ch not in PROTEIN_RESIDUE_MASSES]
        if not known:
            continue
        avg = sum(PROTEIN_RESIDUE_MASSES[ch] for ch in known) + WATER_MASS
        mono = sum(PROTEIN_RESIDUE_MONO[ch] for ch in known) + WATER_MASS
        rows.append({
            "header": header,
            "length": len(s),
            "residues": len(known),
            "unknown": len(unknown),
            "unknown_codes": "".join(sorted(set(unknown))),
            "mw": round(avg, 2),
            "mono": round(mono, 2),
            "kda": round(avg / 1000, 3),
        })
    if not rows:
        raise ValueError("No amino acid residues found")
    return rows


def dna_molecular_weight(text):
    """Single- and double-stranded molecular weight for DNA/RNA sequences."""
    rows = []
    for header, seq in _sequence_records(text):
        s = "".join(ch for ch in seq.upper() if ch.isalpha())
        if not s:
            continue
        has_t, has_u = "T" in s, "U" in s
        if has_t and has_u:
            raise ValueError("Sequence contains both T and U; use DNA or RNA, not a mixture")
        rna = has_u
        table = RNA_RESIDUE_MASSES if rna else DNA_RESIDUE_MASSES
        counts = {ch: s.count(ch) for ch in set(s)}
        known = {ch: n for ch, n in counts.items() if ch in table}
        if not known:
            continue
        length = len(s)
        known_len = sum(known.values())
        ss = sum(table[ch] * n for ch, n in known.items()) + WATER_MASS
        ds = ss * 2
        gc = counts.get("G", 0) + counts.get("C", 0)
        rows.append({
            "header": header,
            "length": length,
            "known": known_len,
            "unknown": length - known_len,
            "type": "RNA" if rna else "DNA",
            "counts": dict(sorted(counts.items())),
            "gc_pct": round(gc / length * 100, 2) if length else 0.0,
            "ss_mw": round(ss, 2),
            "ds_mw": round(ds, 2),
            "ss_kda": round(ss / 1000, 3),
            "ds_kda": round(ds / 1000, 3),
        })
    if not rows:
        raise ValueError("No nucleotide residues found")
    return rows


def primer_tm(text, na_mm=50.0):
    """Wallace and salt-adjusted Tm estimates for DNA primers."""
    rows = []
    for header, seq in _sequence_records(text):
        raw = "".join(ch for ch in seq.upper() if ch.isalpha())
        if not raw:
            continue
        known = "".join(ch for ch in raw if ch in "ACGT")
        if not known:
            continue
        length = len(known)
        gc = known.count("G") + known.count("C")
        gc_pct = round(gc / length * 100, 2)
        wallace = 2 * (length - gc) + 4 * gc
        na = max(float(na_mm or 50.0), 1.0) / 1000.0
        tm_salt = None
        if length >= 14:
            tm_salt = round(81.5 + 16.6 * math.log10(na) + 0.41 * gc_pct - 600.0 / length, 1)
        last5 = known[-5:]
        gc3 = sum(1 for ch in last5 if ch in "GC")
        warnings = []
        if length < 14:
            warnings.append("Shorter than 14 nt: use the Wallace estimate; the salt-adjusted formula is not applied.")
        if length > 30:
            warnings.append("Longer than 30 nt: both formulas are approximate; use a nearest-neighbor tool for critical design.")
        if gc_pct < 40 or gc_pct > 60:
            warnings.append("GC content outside the usual 40-60% primer range.")
        if len(raw) != length:
            warnings.append("Non-ACGT characters were ignored.")
        rows.append({
            "header": header,
            "length": length,
            "gc": gc,
            "gc_pct": gc_pct,
            "unknown": len(raw) - length,
            "wallace": round(wallace, 1),
            "tm_salt": tm_salt,
            "na_mm": float(na_mm or 50.0),
            "gc3": gc3,
            "last5": last5,
            "warnings": warnings,
        })
    if not rows:
        raise ValueError("No DNA bases found")
    return rows
