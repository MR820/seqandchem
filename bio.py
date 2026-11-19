"""FASTA / FASTQ 序列工具（纯 Python 实现，无需 Biopython）"""

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
