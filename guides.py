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
    <tr><td>logP</td><td>1.31</td><td>✅</td></tr>
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
  <li>Quality string — exactly one character per base, ASCII 33-126</li>
</ol>
<p>The FASTQ to FASTA converter rejects a record when those rules are broken: a quality string
   of a different length, a quality character outside that range, a missing line, or a wrapped
   multi-line sequence. It does not drop the quality string and return the sequence anyway.
   Blank lines are allowed between records.</p>

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
"smiles-to-pdbqt-autodock-vina": {
        "path": "/guides/smiles-to-pdbqt-autodock-vina",
        "h1": "SMILES to PDBQT for AutoDock Vina: A Practical Ligand Preparation Guide",
        "title": "SMILES to PDBQT for AutoDock Vina — Ligand Preparation Guide (2026)",
        "description": "A practical workflow for turning a SMILES into a docking-ready PDBQT: "
                       "3D coordinates, protonation, charges, torsions, receptor preparation and "
                       "validation.",
        "lead": "Format conversion is the easy part. A docking-ready ligand also needs the right "
                "protonation, charges and torsions — this guide walks through the whole "
                "preparation.",
        "related": [
            ("/smiles-to-pdbqt", "SMILES → PDBQT"),
            ("/3d", "SMILES → 3D"),
            ("/batch", "Batch converter"),
            ("/api", "API reference"),
        ],
        "prose": """
<p>AutoDock Vina and AutoDock 4 do not read SMILES. They expect a PDBQT file that contains the
   ligand's 3D coordinates, AutoDock atom types, partial charges and a tree of rotatable bonds.
   Converting the text is straightforward; preparing a ligand that behaves correctly in docking is
   the part that needs attention.</p>
<p>This guide covers the full workflow: choosing the protonation state, generating 3D coordinates,
   inspecting the torsion tree, assigning charges, preparing the receptor and validating the
   result. The <a href="/smiles-to-pdbqt">SMILES to PDBQT converter</a> handles the format
   conversion and 3D generation; the rest of the steps are about chemistry, not file formats.</p>

<h2>1. Start from the right structure</h2>
<p>A SMILES string describes connectivity, but docking is sensitive to the protonation state,
   tautomer and charge. Before converting, decide which form you want to dock:</p>
<ul>
  <li><strong>Protonation</strong> — at pH 7.4, carboxylic acids are mostly deprotonated and
      aliphatic amines are mostly protonated. The binding site may favour a different state; if
      the site is known, match the state observed in the co-crystal structure or expected from the
      mechanism.</li>
  <li><strong>Tautomer</strong> — 2-hydroxypyridine and 2-pyridone are the same formula but
      different hydrogen positions. Docking one tautomer can miss the binding mode of the other.</li>
  <li><strong>Salts and counter-ions</strong> — strip counter-ions unless the ion is part of the
      intended ligand. A sodium salt adds atoms and changes the charge.</li>
  <li><strong>Stereochemistry</strong> — define chiral centres with <code>@</code> or
      <code>@@</code>. A flat SMILES cannot produce a stereo-defined 3D conformer.</li>
</ul>
<p>If you are not sure which state to use, prepare the most likely physiological form first, then
   repeat the docking with the alternative if the results are ambiguous.</p>

<h2>2. Generate 3D coordinates</h2>
<p>A PDBQT ligand needs 3D coordinates. A 2D structure or a SMILES without coordinates produces a
   file with all atoms at the same position, which is useless for docking.</p>
<p>The converter generates a force-field-optimised conformer with OpenBabel (MMFF94 when
   parameters are available, UFF otherwise). That is a reasonable starting geometry for a
   drug-like molecule, but it is one local minimum, not an ensemble. For a flexible ligand, inspect
   the conformer and consider generating several starting geometries if the docking protocol
   supports it.</p>

<h2>3. Convert to PDBQT and inspect the torsion tree</h2>
<p>The output contains a ROOT section, one or more BRANCH/ENDBRANCH sections and a TORSDOF line.
   The ROOT is the rigid core; each BRANCH is a flexible branch attached to it; TORSDOF is the
   number of active torsions. Open the file in a text editor and check:</p>
<ul>
  <li>The number of torsions is what you expect. Amide bonds and ring bonds are usually rigid;
      terminal groups may be treated as rigid.</li>
  <li>The atom count matches the molecule. Missing hydrogens or a dropped counter-ion will change
      the count.</li>
  <li>There are no duplicate atoms from multiple models or alternate locations.</li>
</ul>
<p>If the torsion tree looks wrong, fix the structure or adjust the active torsions in
   AutoDockTools before running Vina.</p>

<h2>4. Charges: the step most conversions skip</h2>
<p>PDBQT atom records include a partial charge column. Docking scoring depends on those charges,
   and a file with all zeros is not equivalent to a properly prepared ligand.</p>
<p>OpenBabel's PDBQT writer can produce the atom types and torsion tree but may leave the charge
   column at zero. In the <a href="/smiles-to-pdbqt">converter</a>, this is called out explicitly.
   For production docking, use a preparation tool that assigns Gasteiger or another charge model:</p>
<ul>
  <li><strong>Meeko</strong> — the modern Python preparation tool for AutoDock Vina and
      AutoDock-GPU; it assigns charges and writes PDBQT.</li>
  <li><strong>AutoDockTools</strong> — the classic GUI/command-line preparation suite; assign
      Gasteiger charges before saving the PDBQT.</li>
  <li><strong>Your docking pipeline</strong> — many pipelines wrap ligand preparation and charge
      assignment; use its documented defaults.</li>
</ul>
<p>Whatever tool you use, inspect a few atom records and confirm that the charge column is not all
   zero.</p>

<h2>5. Prepare the receptor separately</h2>
<p>The ligand and the receptor are different preparation problems. For the receptor:</p>
<ol>
  <li>Remove crystallographic waters unless a water is known to mediate binding.</li>
  <li>Remove the co-crystallised ligand and unwanted ions, or keep them deliberately.</li>
  <li>Add hydrogens and assign the protonation state at the intended pH.</li>
  <li>Assign charges and AutoDock atom types, then write a receptor PDBQT.</li>
  <li>Define the search box around the binding site, with enough padding for the ligand.</li>
</ol>
<p>AutoDockTools, Meeko and established docking pipelines provide receptor preparation steps. Do
   not use the ligand converter for a protein unless you have completed these steps separately.</p>

<h2>6. Validate before docking</h2>
<table>
  <thead>
    <tr><th>Check</th><th>What to look for</th></tr>
  </thead>
  <tbody>
    <tr><td>Coordinates</td><td>Atoms are not all at (0,0,0); the conformer is 3D.</td></tr>
    <tr><td>Atom count</td><td>Matches the intended protonation and salt form.</td></tr>
    <tr><td>Charges</td><td>The charge column is not all zero; the model is documented.</td></tr>
    <tr><td>Torsions</td><td>TORSDOF is sensible; amide and ring bonds are not freely rotating.</td></tr>
    <tr><td>Protonation</td><td>Acids, amines and heterocycles match the intended state.</td></tr>
    <tr><td>Receptor</td><td>Waters, co-ligands, hydrogens and charges are intentional.</td></tr>
  </tbody>
</table>

<h2>Common mistakes</h2>
<table>
  <thead>
    <tr><th>Mistake</th><th>Consequence</th></tr>
  </thead>
  <tbody>
    <tr><td>Converting a 2D SMILES without 3D generation</td><td>All atoms at the same coordinates; docking cannot run correctly.</td></tr>
    <tr><td>Accepting zero charges</td><td>Scoring and pose ranking are wrong; results are not comparable to a properly prepared run.</td></tr>
    <tr><td>Docking the wrong tautomer or protonation state</td><td>The correct binding mode may be missed or scored poorly.</td></tr>
    <tr><td>Leaving the counter-ion in the ligand</td><td>Extra atoms and a different net charge; the ligand is no longer the intended molecule.</td></tr>
    <tr><td>Too many active torsions</td><td>A larger search space, slower runs and more false positives.</td></tr>
    <tr><td>Unprepared receptor</td><td>Waters, missing hydrogens or wrong charges distort the site and the score.</td></tr>
  </tbody>
</table>

<h2>Automating the conversion</h2>
<p>For a single ligand, the web page is enough. For a series, the API accepts a SMILES and returns
   a PDBQT:</p>
<pre><code>curl -s https://api.seqandchem.com/api/v1/convert \\
  -H 'Content-Type: application/json' \\
  -d '{"from":"smi","to":"pdbqt","data":"CCO","opts":["--gen3d"]}'</code></pre>
<p>The response contains the PDBQT text in <code>result</code>. The same caveat applies: check the
   charges and protonation before using the output in a production docking campaign. For a
   library, use the <a href="/batch">batch converter</a> and then run a charge-assignment step.</p>

<h2>Frequently asked questions</h2>
<h3>Can I use the SMILES to PDBQT converter for a production docking campaign?</h3>
<p>Use it to generate the 3D structure and the PDBQT skeleton, then assign charges and verify the
   protonation with Meeko, AutoDockTools or your docking pipeline. The converter is a starting
   point, not a complete ligand-preparation protocol.</p>
<h3>Why are the charges in my PDBQT all zero?</h3>
<p>OpenBabel's PDBQT writer does not always assign Gasteiger charges. Use a preparation tool that
   does, or add charges in your pipeline before docking.</p>
<h3>How many torsions should a ligand have?</h3>
<p>There is no fixed number. A rigid ligand may have zero; a flexible drug-like molecule often has
   three to ten. Too many torsions increase the search space and can slow the run or produce more
   false positives.</p>
<h3>Does the converter work for peptides or large ligands?</h3>
<p>The conversion can run, but docking a flexible peptide is a different problem: the search space
   is much larger and the preparation requirements are stricter. Use a protocol designed for
   peptides rather than treating them as small molecules.</p>
<h3>Can I convert a receptor PDB to PDBQT with the same tool?</h3>
<p>The page is intended for small-molecule ligands. Receptor preparation requires removing waters,
   adding hydrogens, assigning charges and defining the search box; use AutoDockTools, Meeko or a
   docking pipeline.</p>
<h3>Is PDBQT the same as PDB?</h3>
<p>No. PDBQT extends PDB with AutoDock atom types, partial charges and a torsion tree. A PDB file
   does not contain the information docking needs.</p>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
{"@type":"Question","name":"Can I use the SMILES to PDBQT converter for a production docking campaign?","acceptedAnswer":{"@type":"Answer","text":"Use it to generate the 3D structure and the PDBQT skeleton, then assign charges and verify the protonation with Meeko, AutoDockTools or your docking pipeline. The converter is a starting point, not a complete ligand-preparation protocol."}},
{"@type":"Question","name":"Why are the charges in my PDBQT all zero?","acceptedAnswer":{"@type":"Answer","text":"OpenBabel's PDBQT writer does not always assign Gasteiger charges. Use a preparation tool that does, or add charges in your pipeline before docking."}},
{"@type":"Question","name":"How many torsions should a ligand have?","acceptedAnswer":{"@type":"Answer","text":"There is no fixed number. A rigid ligand may have zero; a flexible drug-like molecule often has three to ten. Too many torsions increase the search space and can slow the run or produce more false positives."}},
{"@type":"Question","name":"Does the converter work for peptides or large ligands?","acceptedAnswer":{"@type":"Answer","text":"The conversion can run, but docking a flexible peptide is a different problem: the search space is much larger and the preparation requirements are stricter. Use a protocol designed for peptides rather than treating them as small molecules."}},
{"@type":"Question","name":"Can I convert a receptor PDB to PDBQT with the same tool?","acceptedAnswer":{"@type":"Answer","text":"The page is intended for small-molecule ligands. Receptor preparation requires removing waters, adding hydrogens, assigning charges and defining the search box; use AutoDockTools, Meeko or a docking pipeline."}},
{"@type":"Question","name":"Is PDBQT the same as PDB?","acceptedAnswer":{"@type":"Answer","text":"No. PDBQT extends PDB with AutoDock atom types, partial charges and a torsion tree. A PDB file does not contain the information docking needs."}}
]}
</script>
""",
    },
"molecular-weight-average-vs-monoisotopic": {
        "path": "/guides/molecular-weight-average-vs-monoisotopic",
        "h1": "Molecular Weight: Average vs Monoisotopic Mass",
        "title": "Molecular Weight vs Monoisotopic Mass — A Practical Guide (2026)",
        "description": "What average molecular weight and monoisotopic mass actually measure, "
                       "when to use each, and how to calculate them for small molecules, "
                       "proteins and DNA.",
        "lead": "The same molecule has several different \"molecular weights\". Using the wrong one "
                "is a common source of off-by-a-few-daltons errors in mass spectrometry, protein "
                "work and concentration calculations.",
        "related": [
            ("/formula", "Molecular weight calculator"),
            ("/protein-molecular-weight-calculator", "Protein MW calculator"),
            ("/dna-molecular-weight-calculator", "DNA MW calculator"),
            ("/properties", "Property calculator"),
        ],
        "prose": """
<p>\"Molecular weight\" sounds like one number, but a molecule actually has several: the average
   mass, the monoisotopic mass, the nominal mass and the molar mass. They are close for small
   molecules and can differ by tens of daltons for a protein. Using the wrong one is a common
   source of errors in mass spectrometry, gel analysis and concentration calculations.</p>
<p>This guide explains what each number means, how to calculate it from a formula, a SMILES, a
   protein sequence or a DNA sequence, and which one to use for a given task.</p>

<h2>The four numbers</h2>
<table>
  <thead>
    <tr><th>Name</th><th>What it uses</th><th>Typical units</th></tr>
  </thead>
  <tbody>
    <tr><td>Average molecular weight</td><td>Natural isotopic abundance of each element</td><td>Da or g/mol</td></tr>
    <tr><td>Monoisotopic mass</td><td>The most abundant isotope of each element</td><td>Da</td></tr>
    <tr><td>Nominal mass</td><td>Integer mass number of the most abundant isotopes</td><td>Da (integer)</td></tr>
    <tr><td>Molar mass</td><td>Mass of one mole of the substance</td><td>g/mol</td></tr>
  </tbody>
</table>
<p>For practical purposes, average molecular weight and molar mass are the same number with
   different units. Molecular weight is dimensionless and is often reported in daltons; molar mass
   is the mass of one mole and is reported in g/mol. The monoisotopic mass is the one used in
   high-resolution mass spectrometry.</p>

<h2>Why isotopes create the difference</h2>
<p>Most elements are mixtures of isotopes. Carbon, for example, is about 98.9% <sup>12</sup>C and
   1.1% <sup>13</sup>C. The average atomic weight (12.011) reflects that mixture. The monoisotopic
   mass uses only <sup>12</sup>C (exactly 12.000000), so it is slightly lower for a molecule that
   contains carbon.</p>
<p>The difference grows with the number of atoms. For water it is about 0.004 Da; for glucose it is
   about 0.09 Da; for a protein it can be tens of daltons. A mass spectrometer with high resolution
   can resolve the isotope envelope, which is why monoisotopic mass is the right value for MS
   matching.</p>

<h2>Calculating from a formula</h2>
<p>For a formula, sum the atomic weights (average) or the isotope masses (monoisotopic) for every
   atom. For glucose, C<sub>6</sub>H<sub>12</sub>O<sub>6</sub>:</p>
<ul>
  <li><strong>Average:</strong> 6 × 12.011 + 12 × 1.008 + 6 × 15.999 = <strong>180.156 g/mol</strong></li>
  <li><strong>Monoisotopic:</strong> 6 × 12.000000 + 12 × 1.007825 + 6 × 15.994915 =
      <strong>180.0634 Da</strong></li>
</ul>
<p>The <a href="/formula">molecular weight calculator</a> reports the average value and the
   elemental composition. For monoisotopic mass, use a dedicated MS calculator or a tool that
   exposes the isotope masses.</p>

<h2>Calculating from a structure</h2>
<p>For a SMILES or a structure file, the formula is first perceived by OpenBabel and then summed.
   Salts, hydrates and disconnected fragments are included in the total, so strip counter-ions
   first if you want the parent compound. The <a href="/properties">property calculator</a>
   reports molecular weight and formula from a structure; the
   <a href="/formula">molecular weight calculator</a> accepts both formula and SMILES input.</p>

<h2>Proteins and peptides</h2>
<p>A protein is a polymer of amino acids. Its mass is the sum of the residue masses plus one water
   molecule for the free termini. The same calculation applies to a short peptide. For example,
   angiotensin II (<code>DRVYIHPF</code>) has an average mass of <strong>1046.19 Da</strong> and a
   monoisotopic mass of <strong>1045.54 Da</strong>. The
   <a href="/protein-molecular-weight-calculator">protein molecular weight calculator</a> handles
   FASTA input and reports both values.</p>
<p>Post-translational modifications and disulfide bonds are not included in the residue sum. Each
   disulfide bond removes about 2.016 Da; phosphorylation adds about 79.97 Da; acetylation adds
   about 42.01 Da. Add those corrections separately if they are part of the molecule you are
   describing.</p>

<h2>DNA and RNA</h2>
<p>DNA and RNA are polymers of nucleotides. The mass is the sum of the nucleotide residue masses
   plus one water molecule for the free ends. For a double-stranded molecule, the complementary
   strand has the same composition, so the duplex mass is twice the single-strand mass. For the
   39-base sequence <code>ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG</code>, the
   <a href="/dna-molecular-weight-calculator">DNA molecular weight calculator</a> reports
   <strong>12,192.89 Da</strong> for ssDNA and <strong>24,385.77 Da</strong> for dsDNA.</p>
<p>Counter-ions, modified bases and a 5′ phosphate change the mass. Vendors often quote the sodium
   salt or a modified oligo; compare the same form.</p>

<h2>Which number should I use?</h2>
<table>
  <thead>
    <tr><th>Task</th><th>Use</th></tr>
  </thead>
  <tbody>
    <tr><td>Weighing a sample, preparing a solution</td><td>Average molecular weight / molar mass</td></tr>
    <tr><td>SDS-PAGE, gel mobility</td><td>Average molecular weight</td></tr>
    <tr><td>High-resolution mass spectrometry</td><td>Monoisotopic mass</td></tr>
    <tr><td>Peptide mass fingerprinting</td><td>Monoisotopic mass</td></tr>
    <tr><td>Database registration</td><td>Formula and InChI; report the mass method if needed</td></tr>
    <tr><td>Comparing with a vendor's value</td><td>Check which number and which salt form they report</td></tr>
  </tbody>
</table>

<h2>Why two tools give different values</h2>
<ul>
  <li><strong>Average vs monoisotopic</strong> — the most common reason; check which one the tool
      reports.</li>
  <li><strong>Different atomic weight tables</strong> — older tables and newer IUPAC values differ
      slightly.</li>
  <li><strong>Predicted vs measured</strong> — a predicted mass is a calculation; an experimental
      mass includes the actual isotopes and any modifications.</li>
  <li><strong>Salt form and counter-ions</strong> — a sodium salt is heavier than the free acid.</li>
  <li><strong>Modifications and tags</strong> — a His-tag, phosphorylation or a signal peptide
      changes the mass.</li>
</ul>

<h2>Worked examples</h2>
<table>
  <thead>
    <tr><th>Molecule</th><th>Average</th><th>Monoisotopic</th></tr>
  </thead>
  <tbody>
    <tr><td>Water (H<sub>2</sub>O)</td><td>18.015</td><td>18.0106</td></tr>
    <tr><td>Glucose (C<sub>6</sub>H<sub>12</sub>O<sub>6</sub>)</td><td>180.156</td><td>180.0634</td></tr>
    <tr><td>Aspirin (C<sub>9</sub>H<sub>8</sub>O<sub>4</sub>)</td><td>180.159</td><td>180.0423</td></tr>
    <tr><td>Angiotensin II (DRVYIHPF)</td><td>1046.19</td><td>1045.54</td></tr>
    <tr><td>39-mer DNA (single strand)</td><td>12,192.89</td><td>—</td></tr>
  </tbody>
</table>
<p>The DNA row reports the average mass from the calculator; a monoisotopic value would require the
   isotope masses for every nucleotide. For oligonucleotide MS, use a dedicated oligonucleotide
   mass calculator.</p>

<h2>Frequently asked questions</h2>
<h3>What is the difference between molecular weight and monoisotopic mass?</h3>
<p>Molecular weight (average mass) uses the natural abundance of each element. Monoisotopic mass
   uses the most abundant isotope of each element. The monoisotopic value is the one used in
   high-resolution mass spectrometry; the average value is used for weighing and general lab
   calculations.</p>
<h3>Is molecular weight the same as molar mass?</h3>
<p>For practical purposes, yes — the same number, with different units. Molecular weight is
   dimensionless and often reported in Da; molar mass is the mass of one mole and reported in
   g/mol.</p>
<h3>Why is the monoisotopic mass lower than the average mass?</h3>
<p>Because the average includes heavier isotopes such as <sup>13</sup>C and <sup>15</sup>N, while the
   monoisotopic mass uses only the most abundant isotope. For a molecule containing carbon, the
   average is usually slightly higher.</p>
<h3>How do I calculate a protein's molecular weight?</h3>
<p>Sum the residue masses of the amino acids and add one water molecule. The
   <a href="/protein-molecular-weight-calculator">protein molecular weight calculator</a> does
   this from a sequence or FASTA file and reports average and monoisotopic mass.</p>
<h3>How do I calculate DNA molecular weight?</h3>
<p>Sum the nucleotide residue masses and add one water molecule; for double-stranded DNA, double
   the single-strand value. The <a href="/dna-molecular-weight-calculator">DNA molecular weight
   calculator</a> reports both.</p>
<h3>Why do two calculators give different values?</h3>
<p>They may use average vs monoisotopic mass, different atomic weight tables, different salt forms
   or different treatment of modifications. Check the method and the input form before comparing.</p>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
{"@type":"Question","name":"What is the difference between molecular weight and monoisotopic mass?","acceptedAnswer":{"@type":"Answer","text":"Molecular weight, or average mass, uses the natural abundance of each element. Monoisotopic mass uses the most abundant isotope of each element. The monoisotopic value is used in high-resolution mass spectrometry; the average value is used for weighing and general lab calculations."}},
{"@type":"Question","name":"Is molecular weight the same as molar mass?","acceptedAnswer":{"@type":"Answer","text":"For practical purposes, yes, the same number with different units. Molecular weight is dimensionless and often reported in daltons; molar mass is the mass of one mole and reported in grams per mole."}},
{"@type":"Question","name":"Why is the monoisotopic mass lower than the average mass?","acceptedAnswer":{"@type":"Answer","text":"Because the average includes heavier isotopes such as carbon-13 and nitrogen-15, while the monoisotopic mass uses only the most abundant isotope. For a molecule containing carbon, the average is usually slightly higher."}},
{"@type":"Question","name":"How do I calculate a protein's molecular weight?","acceptedAnswer":{"@type":"Answer","text":"Sum the residue masses of the amino acids and add one water molecule. The protein molecular weight calculator does this from a sequence or FASTA file and reports average and monoisotopic mass."}},
{"@type":"Question","name":"How do I calculate DNA molecular weight?","acceptedAnswer":{"@type":"Answer","text":"Sum the nucleotide residue masses and add one water molecule; for double-stranded DNA, double the single-strand value. The DNA molecular weight calculator reports both."}},
{"@type":"Question","name":"Why do two molecular weight calculators give different values?","acceptedAnswer":{"@type":"Answer","text":"They may use average versus monoisotopic mass, different atomic weight tables, different salt forms or different treatment of modifications. Check the method and the input form before comparing."}}
]}
</script>
""",
    },
}

GUIDE_INDEX = {
    "path": "/guides/",
    "h1": "Guides",
    "title": "Chemistry & Bioinformatics Guides — SeqChem",
    "description": "Practical guides on chemical file formats, molecular descriptors, docking "
                   "preparation and sequence formats: SMILES vs InChI, Lipinski's rule of five, "
                   "molecular weight, SMILES to PDBQT, FASTA vs FASTQ.",
}

# Additional practical sections for the guide pages (see seo_copy.py).
from seo_copy import GUIDE_EXTRAS

for _slug, _extra in GUIDE_EXTRAS.items():
    GUIDES[_slug]["prose"] = GUIDES[_slug]["prose"].rstrip() + _extra
