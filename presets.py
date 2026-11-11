"""长尾转换页配置：每个页面有独立的标题、导语和正文，避免重复内容"""

PRESETS = {
    "smiles-to-mol": {
        "from_fmt": "smi", "to_fmt": "mol",
        "h1": "SMILES to MOL Converter",
        "title": "SMILES to MOL Converter — Free Online Chemistry Tool",
        "description": "Convert a SMILES string into an MDL MOL file online. Works with ChemDraw, "
                       "Marvin, Avogadro and any tool that reads the V2000 format.",
        "lead": "Turn a one-line SMILES into a MOL file you can open in a structure editor, "
                "attach to a report, or hand to a colleague.",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
        "prose": """
<h2>Why convert SMILES to MOL?</h2>
<p>SMILES is compact and machine-friendly, but many desktop tools — ChemDraw, MarvinSketch,
   Avogadro, PyMOL — expect a MOL file with an explicit atom and bond table. Converting gives you
   a file with fixed 2D coordinates that opens exactly as drawn, rather than being re-laid-out by
   the receiving application.</p>
<h2>What the output contains</h2>
<p>The result is a V2000 MOL block: a header line, a counts line (number of atoms and bonds), the
   atom block with element symbols and coordinates, and the bond block. Hydrogens are implicit
   unless you enable the option to add them.</p>
<h2>Things to watch for</h2>
<ul>
  <li>MOL files hold exactly one molecule — if your SMILES describes a salt or mixture, only the
      disconnected structure is written.</li>
  <li>Aromatic rings are written in Kekulé form (alternating double bonds), which is what MOL
      requires.</li>
  <li>If you need 3D coordinates for docking, tick “3D coordinates”.</li>
</ul>
""",
    },
    "mol-to-inchi": {
        "from_fmt": "mol", "to_fmt": "inchi",
        "h1": "MOL to InChI Converter",
        "title": "MOL to InChI Converter — Free Online Chemistry Tool",
        "description": "Convert MDL MOL files to standard InChI identifiers online. Useful for "
                       "compound registration and deduplication.",
        "lead": "Turn a MOL file into the IUPAC standard InChI, so the structure can be compared "
                "and stored reliably.",
        "placeholder": "Paste the contents of a .mol file or upload it",
        "prose": """
<h2>Why convert MOL to InChI?</h2>
<p>A MOL file describes one specific drawing of a structure — two drawings of the same compound
   can produce different files. InChI normalises the structure into a canonical string, so two
   different MOL files for aspirin produce the same InChI. That makes it the right form for
   compound registration and duplicate detection.</p>
<h2>What gets preserved</h2>
<p>Connectivity, tautomeric form, charge and stereochemistry are all encoded in separate InChI
   layers. If the MOL file carries wedge/hash bonds, they become the stereo layer of the InChI.</p>
<h2>Common pitfalls</h2>
<ul>
  <li>A MOL file without explicit hydrogens may lose stereo information — check the chiral flags
      in your drawing tool before converting.</li>
  <li>Salts keep their counter-ions in the InChI unless you strip them first.</li>
  <li>To get a fixed-length key instead, convert to InChIKey.</li>
</ul>
""",
    },
    "inchi-to-inchikey": {
        "from_fmt": "inchi", "to_fmt": "inchikey",
        "h1": "InChI to InChIKey Converter",
        "title": "InChI to InChIKey Converter — Free Online Chemistry Tool",
        "description": "Convert InChI strings into the fixed 27-character InChIKey hash, ready to "
                       "use as a database primary key or search term.",
        "lead": "InChI is long and not index-friendly. The InChIKey is a fixed 27-character hash of "
                "the same structure — perfect for databases, URLs and search.",
        "placeholder": "e.g. InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)",
        "prose": """
<h2>InChIKey vs InChI</h2>
<p>The InChIKey is a hash of the InChI. The first 14 characters encode the molecular skeleton and
   the next 8 encode stereochemistry, charge and isotope layers, with a final check character.
   Because it is always 27 characters, it fits neatly into a database column and a URL.</p>
<h2>Where InChIKeys are used</h2>
<ul>
  <li><strong>PubChem, ChEMBL and Wikidata</strong> — all index compounds by InChIKey.</li>
  <li><strong>Structure search</strong> — paste a key into a database to jump straight to a compound.</li>
  <li><strong>Primary keys</strong> — stable, case-sensitive identifiers for a local registry.</li>
</ul>
<h2>Important limitation</h2>
<p>InChIKey is a <em>one-way hash</em>. You cannot recover the structure from it. Always keep the
   InChI or the original structure file alongside the key.</p>
""",
    },
    "pdb-to-smiles": {
        "from_fmt": "pdb", "to_fmt": "smi",
        "h1": "PDB to SMILES Converter",
        "title": "PDB to SMILES Converter — Extract Ligand Structures",
        "description": "Convert PDB protein structures to SMILES online. Useful for extracting "
                       "ligands, cofactors and bound small molecules.",
        "lead": "Pull the chemical structure out of a PDB file — most useful for the small-molecule "
                "ligands and cofactors bound inside a protein structure.",
        "placeholder": "Paste the contents of a .pdb file or upload it",
        "prose": """
<h2>What you actually get</h2>
<p>A PDB file contains a whole protein plus its ligands, waters and ions. Converting to SMILES
   produces a disconnected-format string that tries to represent everything at once, which is
   rarely what you want. The useful workflow is:</p>
<ol>
  <li>Keep only the <code>HETATM</code> records for the ligand you care about.</li>
  <li>Convert that fragment to SMILES.</li>
</ol>
<h2>Typical use cases</h2>
<ul>
  <li>Extracting a bound inhibitor from a crystal structure for similarity searching</li>
  <li>Building a ligand dataset from a set of PDB entries</li>
  <li>Feeding a structure into a docking pipeline</li>
</ul>
<h2>Watch out for</h2>
<p>PDB files often lack hydrogens and bond orders. The converter infers bonds from atom distances,
   so unusual geometries can produce a wrong bonding pattern — always check the result against the
   original figure.</p>
""",
    },
    "smiles-to-cml": {
        "from_fmt": "smi", "to_fmt": "cml",
        "h1": "SMILES to CML Converter",
        "title": "SMILES to CML Converter — Chemical Markup Language",
        "description": "Convert SMILES to CML (Chemical Markup Language) XML online. CML is the "
                       "XML standard for chemical data interchange.",
        "lead": "CML is XML for chemistry — useful when your downstream system expects structured XML "
                "rather than a flat string.",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
        "prose": """
<h2>What is CML?</h2>
<p>Chemical Markup Language is an XML vocabulary that describes molecules as trees of atoms,
   bonds, and properties. Because it is XML, it can be validated with a schema, transformed with
   XSLT, and embedded directly in larger XML documents such as scientific reports or
   instrument data files.</p>
<h2>When CML beats SMILES</h2>
<ul>
  <li>Your pipeline already processes XML (e.g. an ELN export).</li>
  <li>You need to attach arbitrary properties to individual atoms.</li>
  <li>You want a human-readable, diffable structure file.</li>
</ul>
<h2>Size trade-off</h2>
<p>CML is verbose — the same molecule takes 50–100× more bytes than a SMILES string. Use it for
   interchange, not for storing a large library.</p>
""",
    },
    "sdf-to-inchi": {
        "from_fmt": "sdf", "to_fmt": "inchi",
        "h1": "SDF to InChI Converter",
        "title": "SDF to InChI Converter — Batch Compound Registration",
        "description": "Convert every record in an SDF file to an InChI string online. One InChI "
                       "per molecule, same order as the source file.",
        "lead": "Flatten a compound library into canonical InChI strings — the standard step before "
                "registering structures in a database.",
        "placeholder": "Paste SDF records (separated by $$$$) or upload a .sdf file",
        "prose": """
<h2>Registration workflow</h2>
<p>Compound registration requires a canonical representation, and InChI is the usual choice. This
   converter processes every record in an SDF file in one pass, producing one InChI per line in
   the same order as the input records — so you can join the output back to your source table by
   row number.</p>
<h2>What is dropped</h2>
<p>All SDF data fields (name, CAS number, supplier ID, custom properties) are discarded. Only the
   structure survives. If you need to keep annotations, export them separately and merge by record
   order.</p>
<h2>Quality check</h2>
<p>Before registering, scan the output for empty or duplicated InChI values: the first usually
   means a broken record, the second a genuine duplicate in your library.</p>
""",
    },
    "mol2-to-smiles": {
        "from_fmt": "mol2", "to_fmt": "smi",
        "h1": "MOL2 to SMILES Converter",
        "title": "MOL2 to SMILES Converter — Free Online Tool",
        "description": "Convert Tripos MOL2 files to SMILES online. Common when moving structures "
                       "out of docking and molecular modelling tools.",
        "lead": "MOL2 is the Tripos format used by docking and modelling software. Convert it to "
                "SMILES when you need a compact, portable representation.",
        "placeholder": "Paste the contents of a .mol2 file or upload it",
        "prose": """
<h2>Where MOL2 files come from</h2>
<p>MOL2 is the native format of SYBYL and is produced by many modelling packages — docking
   preparation tools, conformer generators and molecular mechanics suites. It carries partial
   charges and atom types that SMILES cannot express.</p>
<h2>What is lost in conversion</h2>
<ul>
  <li><strong>Partial charges</strong> — not represented in SMILES at all.</li>
  <li><strong>SYBYL atom types</strong> — collapsed into plain elements.</li>
  <li><strong>Substructure names</strong> — dropped.</li>
</ul>
<h2>When that matters</h2>
<p>If you are moving a structure into a modelling pipeline that needs charges, do not round-trip
   through SMILES — you will have to re-perceive them. Use SMILES for storage, search, and
   sharing, and keep the MOL2 for the modelling step.</p>
""",
    },
    "xyz-to-smiles": {
        "from_fmt": "xyz", "to_fmt": "smi",
        "h1": "XYZ to SMILES Converter",
        "title": "XYZ to SMILES Converter — From Coordinates to Structure",
        "description": "Convert XYZ coordinate files to SMILES online. The converter infers bonds "
                       "from interatomic distances.",
        "lead": "XYZ only stores atom positions. Converting to SMILES means inferring the bonding "
                "pattern from geometry — handy for structures coming out of quantum chemistry.",
        "placeholder": "Paste XYZ coordinates or upload a .xyz file",
        "prose": """
<h2>How bonds are inferred</h2>
<p>An XYZ file lists element symbols and Cartesian coordinates with no bond information. OpenBabel
   computes an interatomic distance for every atom pair and assigns a bond when the distance falls
   within the covalent radii sum, then perceives bond orders from valence rules.</p>
<h2>Where this works well</h2>
<ul>
  <li>Optimised geometries from quantum chemistry packages (Gaussian, ORCA, Q-Chem)</li>
  <li>Structures exported from molecular dynamics snapshots</li>
  <li>Simple organic molecules with clean, undistorted geometries</li>
</ul>
<h2>Where it fails</h2>
<p>Transition-metal complexes, unusual valences and stretched or compressed bonds often produce
   wrong bond orders. Always compare the SMILES against the structure you started with.</p>
""",
    },
    "smiles-to-xyz": {
        "gen3d_default": True,
        "from_fmt": "smi", "to_fmt": "xyz",
        "h1": "SMILES to XYZ Converter",
        "title": "SMILES to XYZ Converter — 3D Coordinates for QM",
        "description": "Convert SMILES to XYZ coordinate files with generated 3D geometry. Ready as "
                       "input for quantum chemistry calculations.",
        "lead": "Generate a 3D starting geometry from SMILES in the plain XYZ format that quantum "
                "chemistry packages accept.",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
        "prose": """
<h2>Why XYZ for quantum chemistry?</h2>
<p>Most electronic structure packages — Gaussian, ORCA, NWChem, Psi4 — accept a bare list of atoms
   and coordinates as a starting geometry. XYZ is the simplest such format: one line of atom count,
   one comment line, then element and x/y/z for each atom.</p>
<h2>Getting a usable starting structure</h2>
<p>This converter runs a force-field optimisation to build a reasonable 3D conformer before writing
   the coordinates. That is usually enough as a starting point for a geometry optimisation, though
   not a substitute for it.</p>
<h2>What XYZ does not carry</h2>
<ul>
  <li>No bonds — your QM package will perceive them from distances.</li>
  <li>No charge or multiplicity — set those in the input deck.</li>
  <li>No atom labels beyond the element symbol.</li>
</ul>
""",
    },
    "cml-to-smiles": {
        "from_fmt": "cml", "to_fmt": "smi",
        "h1": "CML to SMILES Converter",
        "title": "CML to SMILES Converter — Free Online Tool",
        "description": "Convert Chemical Markup Language (CML) XML files to SMILES strings online.",
        "lead": "CML is readable but bulky. Convert it to SMILES when you need something compact to "
                "store, search or pass to another tool.",
        "placeholder": "Paste CML XML or upload a .cml file",
        "prose": """
<h2>Typical source of CML files</h2>
<p>CML turns up in chemistry-aware XML pipelines: electronic lab notebooks, instrument exports,
   open-data repositories and any system built on XML rather than on a cheminformatics toolkit.
   It is verbose and rarely supported directly by molecular software, which is why converting to
   SMILES is a common first step before doing anything useful with the structure.</p>
<h2>What survives the conversion</h2>
<p>Atoms, bonds, formal charges and explicit stereochemistry are preserved. Atom-level properties
   stored in CML <code>&lt;scalar&gt;</code> elements are dropped, since SMILES has nowhere to put
   them — copy those into your own field before converting if they matter.</p>
<h2>Multi-molecule CML</h2>
<p>A single CML document can hold many molecules, either as separate top-level entries or as
   siblings inside a list. One SMILES per molecule is produced, in document order, so you can map
   the output back to the source by position.</p>
<h2>Round-tripping</h2>
<p>Going CML → SMILES → CML will not reproduce the original file: namespaces, ids, titles and
   custom properties are lost in the first step and not invented in the second. Use this
   conversion when you want the structure, not when you want to preserve the document.</p>
""",
    },
    "pdb-to-sdf": {
        "from_fmt": "pdb", "to_fmt": "sdf",
        "h1": "PDB to SDF Converter",
        "title": "PDB to SDF Converter — Protein Ligands to SDF",
        "description": "Convert PDB structure files to SDF online. Extract ligands and cofactors as "
                       "SDF records for docking or database storage.",
        "lead": "SDF keeps 3D coordinates and per-record metadata, which makes it a better container "
                "than SMILES when the geometry matters.",
        "placeholder": "Paste the contents of a .pdb file or upload it",
        "prose": """
<h2>PDB to SDF vs PDB to SMILES</h2>
<p>Both start from the same file, but SDF preserves the three-dimensional coordinates in the
   original frame. That matters when the ligand's pose inside the binding site is the point — for
   example when preparing a reference ligand for docking or comparing binding modes.</p>
<h2>Practical workflow</h2>
<ol>
  <li>Extract the <code>HETATM</code> records for the ligand of interest.</li>
  <li>Convert that fragment to SDF.</li>
  <li>Add hydrogens and assign charges in your modelling tool.</li>
</ol>
<h2>Caveat</h2>
<p>Crystal structures rarely include hydrogens and may have alternate conformations. Treat the
   converted SDF as a starting point, not a finished ligand.</p>
""",
    },
    "inchi-to-mol": {
        "from_fmt": "inchi", "to_fmt": "mol",
        "h1": "InChI to MOL Converter",
        "title": "InChI to MOL Converter — Free Online Tool",
        "description": "Convert InChI identifiers into MOL structure files online, ready to open in "
                       "a structure editor.",
        "lead": "Got an InChI from a database and need to open it in ChemDraw or Marvin? Convert it "
                "to a MOL file with 2D coordinates.",
        "placeholder": "e.g. InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)",
        "prose": """
<h2>The usual reason</h2>
<p>Public databases hand out InChI strings because they are canonical and unambiguous. Structure
   editors cannot read them. Converting to MOL gives you a file that opens with a sensible 2D
   layout, so you can edit, annotate or export it further.</p>
<h2>What carries over</h2>
<p>InChI encodes connectivity and stereochemistry, so the generated MOL will respect chiral
   centres. Coordinates, however, are generated fresh — the layout will not match whatever the
   original source used.</p>
<h2>Limitation</h2>
<p>If you only have an InChIKey, this will not work. An InChIKey is a hash and cannot be turned
   back into a structure.</p>
""",
    },
    "sdf-to-mol": {
        "from_fmt": "sdf", "to_fmt": "mol",
        "h1": "SDF to MOL Converter",
        "title": "SDF to MOL Converter — Split Structure Files",
        "description": "Convert SDF files to individual MOL files online. Each record becomes one "
                       "MOL structure.",
        "lead": "An SDF is just a sequence of MOL records with data fields attached. Converting to "
                "MOL strips the metadata and gives you individual structures.",
        "placeholder": "Paste SDF records (separated by $$$$) or upload a .sdf file",
        "prose": """
<h2>Why strip the SDF wrapper?</h2>
<p>Many legacy tools and scripts accept only a single-molecule MOL file and choke on the
   <code>$$$$</code> separator and data fields. Converting each record to a plain MOL block makes
   the library compatible with those tools.</p>
<h2>What you lose</h2>
<p>All SDF data fields — compound names, IDs, custom properties — disappear. If those matter, keep
   the original SDF as the system of record and use the MOL files only for the tool that needs
   them.</p>
<h2>Record order</h2>
<p>Records are written in the same order as they appear in the source file, one block per
   molecule.</p>
""",
    },
    "mol-to-sdf": {
        "from_fmt": "mol", "to_fmt": "sdf",
        "h1": "MOL to SDF Converter",
        "title": "MOL to SDF Converter — Add SDF Record Separator",
        "description": "Convert MOL files to SDF format online, adding the record delimiter needed "
                       "by SDF-aware tools.",
        "lead": "MOL and SDF share the same structure block. SDF simply adds a record separator and "
                "an optional data field — which is what many databases and pipelines expect.",
        "placeholder": "Paste the contents of a .mol file or upload it",
        "prose": """
<h2>MOL vs SDF, precisely</h2>
<p>An SDF record is a MOL block followed by zero or more data fields and a line containing
   <code>$$$$</code>. That is the only structural difference. Converting a MOL file to SDF makes it
   acceptable to tools that only read SDF.</p>
<h2>When you need it</h2>
<ul>
  <li>Uploading to a compound database that requires SDF</li>
  <li>Handing structures to an ELN or registration system</li>
  <li>Concatenating several molecules into one multi-record file</li>
</ul>
<h2>Note on data fields</h2>
<p>This conversion does not invent metadata — the record will have a structure block and a
   separator, nothing more. Add data fields in your downstream tool if required.</p>
""",
    },
    "smiles-to-mol2": {
        "gen3d_default": True,
        "from_fmt": "smi", "to_fmt": "mol2",
        "h1": "SMILES to MOL2 Converter",
        "title": "SMILES to MOL2 Converter — For Docking and Modelling",
        "description": "Convert SMILES to Tripos MOL2 files with 3D coordinates, ready for docking "
                       "and molecular modelling tools.",
        "lead": "MOL2 is the Tripos format used by docking preparation and molecular mechanics tools. "
                "This conversion also generates a 3D conformer.",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
        "prose": """
<h2>What MOL2 adds over MOL</h2>
<p>MOL2 assigns a SYBYL atom type to every atom and carries partial charges in the atom block.
   That lets force-field and docking software act on the structure without re-perceiving it. It
   also supports multiple named substructures per record, so a protein–ligand complex can live in
   one file.</p>
<h2>3D geometry is required</h2>
<p>MOL2 is used almost exclusively for three-dimensional work. This converter generates a
   conformer, so the output has real coordinates rather than a flat 2D layout.</p>
<h2>Check before docking</h2>
<ul>
  <li>Hydrogens should be explicit — enable the option if they are missing.</li>
  <li>Charges from atom typing are preliminary; most docking tools re-assign them.</li>
</ul>
""",
    },
    "pdb-to-inchi": {
        "from_fmt": "pdb", "to_fmt": "inchi",
        "h1": "PDB to InChI Converter",
        "title": "PDB to InChI Converter — Standard Identifiers for Ligands",
        "description": "Convert PDB structures to InChI identifiers online, giving you a canonical "
                       "string for each ligand.",
        "lead": "If you need a canonical, database-friendly identifier for a ligand in a crystal "
                "structure, InChI is the target format.",
        "placeholder": "Paste the contents of a .pdb file or upload it",
        "prose": """
<h2>Why InChI rather than SMILES</h2>
<p>PDB files vary in how atoms and bonds are recorded. InChI normalises the result, so two
   structures of the same ligand from different entries produce the same identifier — which is
   exactly what you need for cross-referencing against PubChem or ChEMBL.</p>
<h2>Working with the whole file</h2>
<p>A full PDB includes protein, water and ions. Converting the entire file yields an InChI that
   tries to describe everything at once. For ligand-level identifiers, first extract the
   <code>HETATM</code> records of the molecule you care about.</p>
<h2>Reliability</h2>
<p>Crystal structures often lack hydrogens and may contain alternate conformations. The resulting
   InChI is a best-effort interpretation — verify against the deposited chemical component
   dictionary when precision matters.</p>
""",
    },
    "smiles-to-inchikey": {
        "from_fmt": "smi", "to_fmt": "inchikey",
        "h1": "SMILES to InChIKey Converter",
        "title": "SMILES to InChIKey Converter — 27-Character Compound Key",
        "description": "Convert SMILES directly to the 27-character InChIKey hash online. Ideal for "
                       "database keys and structure lookup.",
        "lead": "Skip the InChI step and go straight from SMILES to the fixed-length InChIKey used by "
                "PubChem, ChEMBL and Wikidata.",
        "placeholder": "e.g. CC(=O)Oc1ccccc1C(=O)O",
        "prose": """
<h2>One line, one key</h2>
<p>The InChIKey is always 27 characters: 14 for the connectivity block, 8 for stereochemistry,
   charge and isotopes, and a final check character. That fixed width makes it cheap to index and
   safe to put in a URL — unlike a full InChI, which can be hundreds of characters.</p>
<h2>What it is good for</h2>
<ul>
  <li>Looking a compound up in PubChem or ChEMBL</li>
  <li>Deduplicating a structure library</li>
  <li>Referencing a structure in a ticket, paper or chat message</li>
</ul>
<h2>What it cannot do</h2>
<p>It is a hash, so it is one-way. Two different molecules producing the same key is astronomically
   unlikely, but you can never recover a structure from a key — always keep the SMILES or InChI.</p>
""",
    },
    "mol2-to-sdf": {
        "from_fmt": "mol2", "to_fmt": "sdf",
        "h1": "MOL2 to SDF Converter",
        "title": "MOL2 to SDF Converter — Free Online Structure Format Tool",
        "description": "Convert Tripos MOL2 files to SDF online, preserving 3D coordinates for "
                       "downstream modelling and database tools.",
        "lead": "Move structures out of modelling software and into the SDF ecosystem without losing "
                "the three-dimensional geometry.",
        "placeholder": "Paste the contents of a .mol2 file or upload it",
        "prose": """
<h2>Why SDF rather than SMILES</h2>
<p>SDF keeps the coordinates and per-record data fields. If you are moving a modelled or docked
   structure into a compound database, that context is worth preserving — SMILES would throw away
   the geometry entirely.</p>
<h2>What is lost</h2>
<p>SYBYL atom types and partial charges are not part of the SDF specification. If downstream tools
   need them, re-run atom typing after conversion rather than assuming they survived.</p>
<h2>Multi-substructure MOL2 files</h2>
<p>Some MOL2 files describe a complex as several named substructures. Converted to SDF, these become
   one record per molecule in the file.</p>
""",
    },
    "xyz-to-sdf": {
        "from_fmt": "xyz", "to_fmt": "sdf",
        "h1": "XYZ to SDF Converter",
        "title": "XYZ to SDF Converter — Add Bonds to Coordinates",
        "description": "Convert XYZ coordinate files to SDF online. Bonds are inferred from geometry "
                       "so the result opens as a proper structure.",
        "lead": "XYZ gives you coordinates only. SDF adds the atom-to-atom bonding that most viewers "
                "and databases need to render and index the structure.",
        "placeholder": "Paste XYZ coordinates or upload a .xyz file",
        "prose": """
<h2>The missing piece: bonds</h2>
<p>An XYZ file is a bare coordinate list — no bonds, no charges, no metadata. Converting to SDF
   requires perceiving bonds from interatomic distances, then assigning bond orders from valence
   rules. The result is a V2000 block that opens in any structure viewer.</p>
<h2>Where this is reliable</h2>
<p>Clean geometries of organic and main-group molecules — typically optimised structures from
   quantum chemistry. Bond perception works well because the geometry is already at a minimum.</p>
<h2>Where it is not</h2>
<p>Transition metals, unusually long or short bonds, and highly distorted snapshots from dynamics
   runs can produce wrong bond orders. Check the output before trusting it.</p>
""",
    },
    "sdf-to-pdb": {
        "from_fmt": "sdf", "to_fmt": "pdb",
        "h1": "SDF to PDB Converter",
        "title": "SDF to PDB Converter — Structure Files for Molecular Viewers",
        "description": "Convert SDF files to PDB format online, for use with molecular viewers and "
                       "structure analysis tools.",
        "lead": "PDB is the lingua franca of molecular viewers. Convert an SDF record when you need to "
                "open it in PyMOL, Chimera or an online viewer.",
        "placeholder": "Paste SDF records (separated by $$$$) or upload a .sdf file",
        "prose": """
<h2>When PDB is the right target</h2>
<p>Molecular graphics tools — PyMOL, ChimeraX, VMD, Jmol — all read PDB natively. They also read
   SDF, but PDB is the format they were designed around, and it is what most structure-alignment and
   contact-analysis scripts expect.</p>
<h2>What changes</h2>
<ul>
  <li>Atom records become <code>HETATM</code> entries with element and coordinate columns.</li>
  <li>Bond orders are not represented — PDB has no bond block, so tools perceive them from
      distances.</li>
  <li>Residue and chain identifiers are assigned generically.</li>
</ul>
<h2>Multi-record SDF</h2>
<p>Each SDF record becomes a separate model in the PDB file, so a small library can be inspected as
   multiple frames in a viewer.</p>
""",
    },
}
