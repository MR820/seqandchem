"""教程文章内容：独立的长文页面，用于内容营销与搜索收录"""

GUIDES = {
    "smiles-inchi-inchikey": {
        "path": "/guides/smiles-inchi-inchikey",
        "h1": "SMILES vs InChI vs InChIKey: What Is the Difference?",
        "title": "SMILES vs InChI vs InChIKey — Differences Explained (2026)",
        "description": "A practical guide to the three common chemical text representations: what "
                       "each encodes, when to use it, and why SMILES is not a safe database key.",
        "lead": "Three text formats describe the same molecule in three different ways. Choosing "
                "the wrong one is a common source of duplicate records and broken lookups.",
        "related": [
            ("/smiles-to-inchi", "SMILES → InChI"),
            ("/inchi-to-smiles", "InChI → SMILES"),
            ("/smiles-to-inchikey", "SMILES → InChIKey"),
            ("/inchi-to-inchikey", "InChI → InChIKey"),
        ],
        "prose": """
<p>If you have ever tried to match compounds across two databases and found that the same molecule
   appears twice, the culprit is usually the representation format. SMILES, InChI and InChIKey all
   describe a structure, but they differ in what they guarantee — and only one of them is safe as a
   primary key.</p>

<h2>SMILES: compact, human-writable, not canonical</h2>
<p>SMILES (Simplified Molecular Input Line Entry System) writes a molecule as a traversal of its
   graph. Atoms are element symbols, bonds are implicit or written as <code>-</code>, <code>=</code>,
   <code>#</code>, branches use parentheses and rings use digit closures.</p>
<p>Aspirin, for example, can be written as:</p>
<pre><code>CC(=O)Oc1ccccc1C(=O)O
OC(=O)c1ccccc1OC(C)=O
O=C(O)c1ccccc1OC(=O)C</code></pre>
<p>All three are valid and describe the same molecule. That flexibility is exactly the problem: a
   string comparison of two SMILES is <em>not</em> a comparison of two molecules.</p>
<h3>What SMILES is good for</h3>
<ul>
  <li>Pasting into a structure editor or drawing tool</li>
  <li>Compact storage inside a script or a database column you control</li>
  <li>SMARTS substructure queries (SMARTS is SMILES extended with wildcards)</li>
  <li>Input to almost every cheminformatics toolkit</li>
</ul>
<h3>What SMILES is bad for</h3>
<ul>
  <li>Deduplication — unless you canonicalise first</li>
  <li>Cross-database lookup — different toolkits canonicalise differently</li>
  <li>Regulatory or archival identifiers</li>
</ul>
<p>Most toolkits do have a canonical SMILES algorithm, but "canonical" is toolkit-specific. RDKit's
   canonical SMILES and OpenBabel's canonical SMILES are both deterministic and both perfectly
   valid — and they are not guaranteed to produce the same string. That makes canonical SMILES a
   good internal key and a poor external one.</p>

<h2>InChI: canonical by standard</h2>
<p>InChI (International Chemical Identifier) is maintained by IUPAC and designed specifically to be
   a canonical, non-proprietary identifier. Every conforming implementation must produce the same
   string for the same structure. The format is layered:</p>
<pre><code>InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)</code></pre>
<ul>
  <li><code>1S</code> — version 1, standard InChI</li>
  <li><code>C9H8O4</code> — molecular formula layer</li>
  <li><code>c1-6(10)13-...</code> — connectivity layer</li>
  <li><code>h2-5H,1H3,(H,11,12)</code> — hydrogen layer</li>
</ul>
<p>Separate layers also cover charge, stereochemistry (including <code>/t</code> and <code>/m</code>
   sub-layers) and isotopes. If a structure has no stereo, those layers are simply absent.</p>
<h3>Why InChI exists</h3>
<p>Before InChI, every vendor had its own canonical form. InChI gave the community a single
   reference string that could be published in a paper or deposited with a patent and re-derived
   later by anyone. PubChem, ChEMBL, Wikidata and most patent databases index by InChI and
   InChIKey.</p>
<h3>The downside: length</h3>
<p>A full InChI is long, contains punctuation that needs escaping in URLs, and grows with molecule
   complexity. For a small molecule it is ~60 characters; for a peptide or a natural product it can
   be hundreds. Indexing millions of them is possible but not free.</p>

<h2>InChIKey: fixed-width hash</h2>
<p>The InChIKey is a hash of the InChI, always exactly 27 characters:</p>
<pre><code>BSYNRYMUTXBXSQ-UHFFFAOYSA-N</code></pre>
<p>The three blocks are meaningful:</p>
<ul>
  <li><strong>First 14</strong> — the molecular skeleton (connectivity plus formula)</li>
  <li><strong>Next 8</strong> — stereochemistry, charge and isotope layers</li>
  <li><strong>Final 1</strong> — a check character to catch transcription errors</li>
</ul>
<p>Because the first block ignores stereo, two enantiomers share the same 14-character prefix and
   differ only in the second block. That is convenient for "find me anything with this skeleton"
   queries.</p>
<h3>What InChIKey cannot do</h3>
<p>It is a one-way hash. You cannot recover a structure from a key, and you cannot convert a key
   into anything else. Keep the InChI or the original structure file alongside it. Also note that
   the key is case-sensitive — <code>BSYNRYMUTXBXSQ-UHFFFAOYSA-N</code> and its lowercase form are
   different strings to a database.</p>

<h2>Which one should you use?</h2>
<table>
  <thead><tr><th>Task</th><th>Use</th></tr></thead>
  <tbody>
    <tr><td>Pasting into a drawing tool</td><td>SMILES</td></tr>
    <tr><td>Deduplicating a library</td><td>InChI (or InChIKey)</td></tr>
    <tr><td>Primary key in a database</td><td>InChIKey, with InChI stored alongside</td></tr>
    <tr><td>Matching against PubChem / ChEMBL</td><td>InChIKey</td></tr>
    <tr><td>SMARTS substructure search</td><td>SMILES / SMARTS</td></tr>
    <tr><td>Filing a patent or a regulatory dossier</td><td>InChI</td></tr>
  </tbody>
</table>

<h2>Converting between them</h2>
<p>All three conversions are one click on this site: <a href="/smiles-to-inchi">SMILES to InChI</a>,
   <a href="/inchi-to-smiles">InChI to SMILES</a>, <a href="/smiles-to-inchikey">SMILES to
   InChIKey</a> and <a href="/inchi-to-inchikey">InChI to InChIKey</a>. Two rules of thumb:</p>
<ul>
  <li>Always convert <em>toward</em> InChI when you cross a system boundary, never away from it.</li>
  <li>Never rely on a SMILES string being stable across tools; canonicalise at the point of entry.</li>
</ul>
""",
    },
    "lipinski-rule-of-five": {
        "path": "/guides/lipinski-rule-of-five",
        "h1": "Lipinski's Rule of Five: A Practical Guide",
        "title": "Lipinski Rule of Five Explained — With Worked Examples",
        "description": "What the rule of five actually says, where the numbers come from, how to "
                       "apply it to a SMILES string, and the cases where passing it means very "
                       "little.",
        "lead": "The rule of five is the most quoted heuristic in drug discovery and the most "
                "misused. Here is what it measures, what it does not, and how to run it on a "
                "molecule in seconds.",
        "related": [
            ("/lipinski", "Drug-likeness checker"),
            ("/properties", "Property calculator"),
            ("/guides/fasta-vs-fastq", "FASTA vs FASTQ"),
        ],
        "prose": """
<p>The rule of five was published by Christopher Lipinski and colleagues in 1997, based on an
   analysis of compounds that made it into clinical trials versus those that failed. It is a set of
   four thresholds, each involving the number five or a multiple of it — hence the name.</p>

<h2>The four rules</h2>
<table>
  <thead><tr><th>Property</th><th>Threshold</th><th>What it reflects</th></tr></thead>
  <tbody>
    <tr><td>Molecular weight</td><td>≤ 500 Da</td><td>Size — large molecules diffuse poorly</td></tr>
    <tr><td>logP (octanol/water)</td><td>≤ 5</td><td>Lipophilicity — too greasy means poor solubility</td></tr>
    <tr><td>Hydrogen bond donors (HBD)</td><td>≤ 5</td><td>Count of N–H and O–H groups</td></tr>
    <tr><td>Hydrogen bond acceptors (HBA)</td><td>≤ 10</td><td>Count of N and O atoms</td></tr>
  </tbody>
</table>
<p>The usual interpretation is "no more than one violation". Two or more violations is where the
   probability of poor oral absorption rises sharply.</p>

<h2>Where the numbers come from — and what they really mean</h2>
<p>The thresholds were not derived from first principles. They are the 90th percentile of the
   distribution for compounds that reached phase II trials. In other words: the rule describes the
   space that historically successful oral drugs occupied, not a physical law.</p>
<p>That has two consequences worth remembering:</p>
<ul>
  <li><strong>Passing the rule does not make a compound a drug.</strong> It makes it statistically
      similar to ones that entered trials.</li>
  <li><strong>Failing the rule does not make a compound useless.</strong> Many antibiotics,
      antifungals, PROTACs and natural products are far outside the space and work very well.</li>
</ul>

<h2>Worked example: aspirin</h2>
<p>SMILES: <code>CC(=O)Oc1ccccc1C(=O)O</code></p>
<table>
  <thead><tr><th>Property</th><th>Value</th><th>Pass?</th></tr></thead>
  <tbody>
    <tr><td>MW</td><td>180.16</td><td>✅</td></tr>
    <tr><td>logP</td><td>1.19</td><td>✅</td></tr>
    <tr><td>HBD</td><td>1 (the carboxylic acid OH)</td><td>✅</td></tr>
    <tr><td>HBA</td><td>4 (three O, one carbonyl O counted separately)</td><td>✅</td></tr>
  </tbody>
</table>
<p>Aspirin passes on all four. Run the same input through the <a href="/lipinski">drug-likeness
   checker</a> and you get the same table in one request.</p>

<h2>The Veber extensions</h2>
<p>Lipinski's rule says nothing about flexibility, which turns out to matter for oral
   bioavailability. Veber et al. (2002) added two criteria that are now usually reported alongside:</p>
<ul>
  <li><strong>Rotatable bonds ≤ 10</strong> — fewer conformations, better absorption</li>
  <li><strong>Polar surface area (TPSA) ≤ 140 Å²</strong> — beyond this, passive permeability drops</li>
</ul>
<p>A molecule can pass Lipinski and fail Veber — a long flexible chain with one polar group, for
   example. Reporting both gives a much more honest picture, which is why our
   <a href="/lipinski">checker</a> shows all six numbers.</p>

<h2>Common mistakes</h2>
<h3>Counting hydrogen bond acceptors wrong</h3>
<p>Lipinski's HBA count is the sum of nitrogen and oxygen atoms, not the number of lone pairs and
   not the number of acceptor <em>groups</em>. A nitro group counts as three, a carboxylate as two.</p>
<h3>Using logP when you mean logD</h3>
<p>The rule uses logP — the partition coefficient of the neutral form. At physiological pH, an
   ionisable acid or base has a very different effective lipophilicity (logD). A carboxylic acid
   with logP 4.5 may have logD near 1 at pH 7.4. If you are reasoning about absorption, logD is
   usually the more relevant number.</p>
<h3>Applying it to biologics</h3>
<p>The rule was derived from small molecules. Applying MW ≤ 500 to an antibody or a peptide is
   meaningless — those molecules are designed to work by entirely different mechanisms.</p>

<h2>Use it as a filter, not a verdict</h2>
<p>The most useful application is triage: run a large library through the rule, flag compounds with
   two or more violations, and spend your synthesis budget elsewhere first. Keep the flag, not the
   decision. <a href="/lipinski">Run the checker</a> on any SMILES string, or paste a whole library
   into the <a href="/batch">batch converter</a> to compute properties in bulk.</p>
""",
    },
    "fasta-vs-fastq": {
        "path": "/guides/fasta-vs-fastq",
        "h1": "FASTA vs FASTQ: What Is the Difference?",
        "title": "FASTA vs FASTQ — Format Differences, Examples and Conversion",
        "description": "How FASTA and FASTQ differ, what the quality scores in FASTQ mean (Phred), "
                       "when to convert between them, and what you lose in each direction.",
        "lead": "Both formats hold nucleotide sequences. One carries per-base quality scores and one "
                "does not — and that single difference decides which pipelines will accept your "
                "file.",
        "related": [
            ("/bio/fasta-to-fastq", "FASTA → FASTQ"),
            ("/bio/fastq-to-fasta", "FASTQ → FASTA"),
            ("/bio/gc-content", "GC content calculator"),
            ("/bio/", "All sequence tools"),
        ],
        "prose": """
<p>FASTA and FASTQ are the two workhorse text formats of bioinformatics. FASTA is older and simpler;
   FASTQ was introduced with next-generation sequencing to carry a per-base confidence score
   alongside each base.</p>

<h2>FASTA</h2>
<p>A FASTA record is a header line beginning with <code>&gt;</code> followed by one or more lines of
   sequence:</p>
<pre><code>&gt;seq1 sample description
ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG
&gt;seq2
ATGGCCTTTGTAATGGGCCGCTGAAAGGGTGCCCGATAG</code></pre>
<p>Sequence lines are conventionally wrapped at 60 or 70 characters, but any width is legal. A file
   can hold any number of records.</p>
<h3>What FASTA is used for</h3>
<ul>
  <li>Reference genomes and transcriptomes</li>
  <li>Protein sequences</li>
  <li>BLAST databases</li>
  <li>Multiple sequence alignment input</li>
  <li>Anywhere the sequence itself is the payload and per-base confidence is irrelevant</li>
</ul>

<h2>FASTQ</h2>
<p>A FASTQ record has four lines:</p>
<pre><code>@read1
ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII</code></pre>
<ol>
  <li><code>@</code> header — same content as a FASTA header, different marker</li>
  <li>Sequence</li>
  <li><code>+</code> separator, optionally repeating the header</li>
  <li>Quality string — exactly one character per base</li>
</ol>

<h2>What the quality string means</h2>
<p>Each character encodes a Phred quality score Q, which is a log-scale estimate of the probability
   that the base is wrong:</p>
<pre><code>Q = -10 × log10(P_error)</code></pre>
<p>The character is the score plus an offset. Modern Illumina data uses Phred+33 (Sanger encoding),
   so:</p>
<table>
  <thead><tr><th>Character</th><th>ASCII</th><th>Phred Q</th><th>Error probability</th></tr></thead>
  <tbody>
    <tr><td><code>!</code></td><td>33</td><td>0</td><td>1 in 1</td></tr>
    <tr><td><code>+</code></td><td>43</td><td>10</td><td>1 in 10</td></tr>
    <tr><td><code>5</code></td><td>53</td><td>20</td><td>1 in 100</td></tr>
    <tr><td><code>?</code></td><td>63</td><td>30</td><td>1 in 1,000</td></tr>
    <tr><td><code>I</code></td><td>73</td><td>40</td><td>1 in 10,000</td></tr>
  </tbody>
</table>
<p>Older Illumina pipelines used Phred+64, which produces characters like <code>h</code> for a
   decent score. Mixing the two encodings silently corrupts quality interpretation — one of the
   reasons FASTQ files carry a "encoding" note in their metadata.</p>

<h2>Converting FASTQ to FASTA</h2>
<p>This throws away the quality string. It is a one-line transformation per record, and it is
   completely safe — but it is also <strong>irreversible</strong>. Once the quality data is gone it
   cannot be reconstructed.</p>
<p>Convert when:</p>
<ul>
  <li>Your downstream tool only accepts FASTA (BLAST, most aligners' reference input)</li>
  <li>You are assembling or annotating and quality has already been used for filtering</li>
  <li>You need a compact archive of the sequences</li>
</ul>
<p>Do <em>not</em> convert when you still need to trim, filter or call variants — those steps depend
   on the quality scores.</p>

<h2>Converting FASTA to FASTQ</h2>
<p>Going the other way is synthesising information that never existed. You cannot invent real
   quality scores, so any converter has to write a placeholder. Ours writes the highest quality
   character throughout, which means "assume every base is correct".</p>
<p>This is legitimate when an old tool insists on FASTQ input but you genuinely have no quality
   data — for example a sequence reconstructed from a paper. It is <em>not</em> legitimate for
   feeding an aligner that will use those scores to decide which mismatches to trust.</p>

<h2>Quick reference</h2>
<table>
  <thead><tr><th></th><th>FASTA</th><th>FASTQ</th></tr></thead>
  <tbody>
    <tr><td>Header marker</td><td><code>&gt;</code></td><td><code>@</code></td></tr>
    <tr><td>Lines per record</td><td>2+ (wrapped)</td><td>exactly 4</td></tr>
    <tr><td>Quality scores</td><td>no</td><td>yes, one per base</td></tr>
    <tr><td>Typical size</td><td>1× sequence</td><td>~2× sequence</td></tr>
    <tr><td>Typical source</td><td>reference, protein</td><td>sequencer output</td></tr>
  </tbody>
</table>

<h2>Try it</h2>
<p>Convert in either direction with <a href="/bio/fasta-to-fastq">FASTA → FASTQ</a> or
   <a href="/bio/fastq-to-fasta">FASTQ → FASTA</a>, or compute GC content and sequence statistics
   with the <a href="/bio/gc-content">GC content calculator</a>. All of them run locally in Python
   on this server — nothing is sent to a third party.</p>
""",
    },
}

GUIDE_INDEX = {
    "path": "/guides/",
    "h1": "Guides",
    "title": "Chemistry & Bioinformatics Guides — SeqChem",
    "description": "Practical guides on chemical file formats, molecular descriptors and sequence "
                   "formats: SMILES vs InChI, Lipinski's rule of five, FASTA vs FASTQ.",
}
