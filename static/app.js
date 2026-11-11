/* SeqChem shared front-end */
(function () {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  let FORMATS = [];
  let convBinary = null;
  let viewerConv = null;
  let viewer3d = null;
  let lastSdf = "";
  let lastSvg = "";

  /* ── 通用 ── */
  function setStatus(sel, msg, kind) {
    const el = $(sel);
    if (!el) return;
    el.textContent = msg || "";
    el.className = "status" + (kind ? " " + kind : "");
  }

  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  }

  async function loadFormats() {
    try {
      const r = await fetch("/api/formats");
      const j = await r.json();
      FORMATS = j.items || [];
    } catch (e) {
      FORMATS = [];
    }
    $$("select[data-fmt]").forEach((sel) => {
      const dir = sel.dataset.dir || "read";
      const def = sel.dataset.default || "smi";
      const list = FORMATS.filter((f) => (dir === "write" ? f.write : f.read));
      sel.innerHTML = list
        .map((f) => `<option value="${f.id}">${f.id} — ${f.desc}</option>`)
        .join("");
      sel.value = def;
    });
  }

  /* ── 示例 ── */
  const EXAMPLE_INPUT = {
    conv: "#conv-input", prop: "#prop-input", depict: "#depict-input",
    mol3d: "#mol3d-input", sub: "#sub-input", lip: "#lip-input",
    batch: "#batch-input", bio: "#bio-input", iupac: "#iupac-input",
  };
  const EXAMPLE_FORMAT = {
    conv: "#conv-from", prop: "#prop-from", depict: "#depict-from",
    mol3d: "#mol3d-from", sub: "#sub-from", lip: "#lip-from", batch: "#batch-from",
  };

  async function loadExample(tab) {
    const input = $(EXAMPLE_INPUT[tab]);
    if (!input) return;

    if (tab === "iupac") {
      input.value = [
        "2-acetoxybenzoic acid",
        "(2R)-2-hydroxypropanoic acid",
        "2,3,4,5,6-pentahydroxyhexanal",
        "N-(4-hydroxyphenyl)acetamide",
        "1,3,7-trimethylpurine-2,6-dione",
        "4-aminobenzoic acid",
        "aspirin",
      ].join("\n");
      return;
    }

    if (tab === "batch") {
      const sel2 = $("#batch-from");
      if (sel2) sel2.value = "smi";
      input.value = ["c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "C1CCCCC1", "CC(=O)O", "CCO"].join("\n");
      return;
    }

    if (tab === "bio") {
      const op = ($("#bio-tool") || {}).dataset ? $("#bio-tool").dataset.op : "";
      const samples = {
        fasta2fastq: ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
        fastq2fasta: "@read1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG\n+\nIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",
        stats: ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG\n>seq2\nGCGCGCGCGCGCGCGCGCGC",
        revcomp: ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
        translate: ">seq1\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
      };
      input.value = samples[op] || "";
      return;
    }

    if (tab === "sub") {
      const subSel = $(EXAMPLE_FORMAT[tab]);
      if (subSel) subSel.value = "smi";
      input.value = ["c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "C1CCCCC1"].join("\n");
      return;
    }

    const sel = $(EXAMPLE_FORMAT[tab]);
    if (!sel) return;

    input.value = "…";
    try {
      const r = await fetch("/api/example?format=" + encodeURIComponent(sel.value));
      const j = await r.json();
      input.value = j.ok ? j.data : "";
    } catch (e) {
      input.value = "";
    }
  }

  function bindExamples() {
    $$("[data-example]").forEach((btn) => {
      btn.addEventListener("click", () => loadExample(btn.dataset.example));
    });
  }

  function bindFiles() {
    // Any <input type="file"> works: it fills the textarea named by data-target.
    // Older ids are kept as fallbacks so existing markup keeps working.
    const legacy = { "batch-file": "#batch-input", "bio-file": "#bio-input" };
    $$('input[type="file"]').forEach((file) => {
      const target = file.dataset.target || legacy[file.id];
      if (!target || !$(target)) return;
      file.addEventListener("change", () => {
        const picked = file.files[0];
        if (!picked) return;
        const reader = new FileReader();
        reader.onload = () => {
          $(target).value = reader.result;
          const status = $(target.replace("-input", "-status"));
          if (status) {
            status.className = "status ok";
            const kb = picked.size < 1024 ? `${picked.size} B` : `${Math.round(picked.size / 1024)} KB`;
            status.textContent = `Loaded ${picked.name} (${kb})`;
          }
        };
        reader.readAsText(picked);
      });
    });
  }

  function bindCopy() {
    $$("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const text = $("#" + btn.dataset.copy).textContent || "";
        try {
          await navigator.clipboard.writeText(text);
          const old = btn.textContent;
          btn.textContent = "Copied";
          setTimeout(() => (btn.textContent = old), 1200);
        } catch (e) { /* ignore */ }
      });
    });
  }

  /* ── 3D 渲染（共用） ── */
  function makeViewer(el) {
    if (!window.$3Dmol || !el) return null;
    return window.$3Dmol.createViewer(el, { backgroundColor: "#ffffff" });
  }

  function applyStyle(viewer, kind) {
    if (kind === "sphere") viewer.setStyle({}, { sphere: { scale: 0.32 } });
    else if (kind === "line") viewer.setStyle({}, { line: { linewidth: 2 } });
    else viewer.setStyle({}, { stick: { radius: 0.16 } });
  }

  /* ── 页面：转换 ── */
  function showConvResult(j) {
    const preview = $("#conv-preview");
    const pre = $("#conv-out");
    const toggle = $("#conv-toggle");

    renderConv3d(j.preview_sdf || null);

    if (j.binary) {
      convBinary = { dataUrl: j.data_url, ext: (j.mime || "").split("/")[1] || "bin" };
      const isImage = (j.mime || "").indexOf("image/") === 0;
      pre.textContent = "";
      if (isImage) {
        preview.style.display = "grid";
        preview.innerHTML = '<img src="' + j.data_url + '" style="max-width:100%;height:auto" alt="preview" />';
        pre.style.display = "none";
        toggle.style.display = "none";
      } else {
        preview.style.display = "grid";
        preview.innerHTML =
          '<div style="text-align:center"><p style="color:var(--muted);font-size:14px">' +
          (j.size / 1048576).toFixed(1) + ' MB</p><a class="btn" download="output.' +
          convBinary.ext + '" href="' + j.data_url + '">Download</a></div>';
        pre.style.display = "none";
        toggle.style.display = "none";
      }
      return;
    }

    if (j.is_image) {
      convBinary = null;
      preview.style.display = "grid";
      preview.innerHTML = j.result;
      pre.textContent = j.result;
      pre.style.display = "none";
      toggle.style.display = "";
      toggle.dataset.mode = "preview";
      toggle.textContent = "View source";
      return;
    }

    convBinary = null;
    preview.style.display = "none";
    preview.innerHTML = "";
    pre.style.display = "";
    pre.textContent = j.result || "";
    toggle.style.display = "none";
  }

  function renderConv3d(sdf) {
    const wrap = $("#conv-3d-wrap");
    const el = $("#conv-3d");
    if (!wrap || !el) return;
    if (!sdf || !window.$3Dmol) { wrap.style.display = "none"; return; }
    wrap.style.display = "block";
    if (!viewerConv) viewerConv = makeViewer(el);
    if (!viewerConv) return;
    viewerConv.removeAllModels();
    viewerConv.addModel(sdf, "sdf");
    applyStyle(viewerConv, "stick");
    viewerConv.zoomTo();
    viewerConv.render();
    viewerConv.resize();
  }

  async function runConvert() {
    const data = $("#conv-input").value;
    if (!data.trim()) return setStatus("#conv-status", "Please enter molecule data", "err");
    const opts = $$(".chips input:checked").map((c) => c.value);
    setStatus("#conv-status", "Working…", "");
    const j = await postJSON("/api/convert", {
      data, from: $("#conv-from").value, to: $("#conv-to").value, opts,
    });
    if (!j.ok) {
      setStatus("#conv-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    showConvResult(j);
    setStatus("#conv-status", "Done" + (j.log ? " · " + j.log : ""), "ok");
  }

  /* ── 页面：属性 ── */
  async function runProps() {
    const data = $("#prop-input").value;
    if (!data.trim()) return setStatus("#prop-status", "Please enter molecule data", "err");
    setStatus("#prop-status", "Working…", "");
    const j = await postJSON("/api/properties", { data, from: $("#prop-from").value });
    if (!j.ok) {
      setStatus("#prop-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    const rows = j.rows || [];
    if (!rows.length) return setStatus("#prop-status", "No result", "err");
    const order = Object.keys(j.labels);
    const head = "<tr><th>#</th>" + order.map((k) => `<th>${j.labels[k]}</th>`).join("") + "</tr>";
    const body = rows
      .map((r, i) =>
        "<tr><td>" + (i + 1) + "</td>" +
        order.map((k) => `<td>${(r.props[k] || "").replace(/</g, "&lt;")}</td>`).join("") + "</tr>")
      .join("");
    $("#prop-result").style.display = "block";
    $("#prop-result").innerHTML = `<div style="overflow:auto"><table>${head}${body}</table></div>`;
    setStatus("#prop-status", "Done", "ok");
  }

  /* ── 页面：结构图 ── */
  async function runDepict() {
    const data = $("#depict-input").value;
    if (!data.trim()) return setStatus("#depict-status", "Please enter molecule data", "err");
    setStatus("#depict-status", "Working…", "");
    const j = await postJSON("/api/depict", { data, from: $("#depict-from").value });
    if (!j.ok) {
      setStatus("#depict-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    lastSvg = j.svg;
    $("#depict-out").innerHTML = j.svg;
    setStatus("#depict-status", "Done", "ok");
  }

  /* ── 页面：3D ── */
  async function runMol3d() {
    const data = $("#mol3d-input").value;
    if (!data.trim()) return setStatus("#mol3d-status", "Please enter molecule data", "err");
    setStatus("#mol3d-status", "Generating conformer…", "");
    const j = await postJSON("/api/gen3d", { data, from: $("#mol3d-from").value });
    if (!j.ok) {
      setStatus("#mol3d-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    const el = $("#mol3d-out");
    if (!viewer3d) viewer3d = makeViewer(el);
    if (viewer3d) {
      viewer3d.removeAllModels();
      viewer3d.addModel(j.result, "sdf");
      applyStyle(viewer3d, $("#mol3d-style").value);
      viewer3d.zoomTo();
      viewer3d.render();
      viewer3d.resize();
    }
    lastSdf = j.result;
    setStatus("#mol3d-status", "Done", "ok");
  }

  /* ── 页面：子结构 ── */
  async function runSub() {
    const data = $("#sub-input").value;
    if (!data.trim()) return setStatus("#sub-status", "Please enter molecule data", "err");
    setStatus("#sub-status", "Working…", "");
    const j = await postJSON("/api/substructure", {
      data, from: $("#sub-from").value, smarts: $("#sub-smarts").value,
    });
    if (!j.ok) {
      setStatus("#sub-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    $("#sub-result").style.display = "block";
    const list = (j.matches || [])
      .map((m) => `<pre style="max-height:none;margin-bottom:8px">${m}</pre>`)
      .join("");
    $("#sub-result").innerHTML =
      `<div><span class="badge">Matches: ${j.count}</span></div>` +
      (list || '<p style="color:var(--muted)">No match</p>');
    setStatus("#sub-status", "Done", "ok");
  }

  /* ── 页面：相似度 ── */
  async function runSim() {
    setStatus("#sim-status", "Working…", "");
    const j = await postJSON("/api/similarity", {
      a: $("#sim-a").value, b: $("#sim-b").value,
      from: $("#sim-from").value, fp: $("#sim-fp").value,
    });
    if (!j.ok) {
      setStatus("#sim-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    $("#sim-result").style.display = "block";
    $("#sim-result").innerHTML =
      `<label>Tanimoto similarity</label><div class="metric">${j.tanimoto.toFixed(4)}</div>` +
      `<div class="hint">bits A: ${j.bits_a} · bits B: ${j.bits_b} · common: ${j.common} · union: ${j.union}</div>`;
    setStatus("#sim-status", "Done", "ok");
  }

  /* ── 页面：Lipinski ── */
  function num(v) {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : null;
  }

  async function runLipinski() {
    const data = $("#lip-input").value;
    if (!data.trim()) return setStatus("#lip-status", "Please enter molecule data", "err");
    setStatus("#lip-status", "Working…", "");

    const j = await postJSON("/api/properties", { data, from: $("#lip-from").value });
    if (!j.ok) {
      setStatus("#lip-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    const rows = j.rows || [];
    if (!rows.length) return setStatus("#lip-status", "No result", "err");

    const rules = [
      { key: "MW", label: "Molecular weight", limit: "≤ 500 Da", max: 500, group: "ro5" },
      { key: "logP", label: "logP", limit: "≤ 5", max: 5, group: "ro5" },
      { key: "HBD", label: "H-bond donors", limit: "≤ 5", max: 5, group: "ro5" },
      { key: "HBA1", label: "H-bond acceptors", limit: "≤ 10", max: 10, group: "ro5" },
      { key: "TPSA", label: "TPSA", limit: "≤ 140 Å²", max: 140, group: "veber" },
      { key: "rotors", label: "Rotatable bonds", limit: "≤ 10", max: 10, group: "veber" },
    ];

    let html = "";
    rows.forEach((row, idx) => {
      let violations = 0;
      let veber = 0;
      const body = rules
        .map((r) => {
          const val = num(row.props[r.key]);
          if (val === null) {
            return `<tr><td>${r.label}</td><td>—</td><td>${r.limit}</td><td><span class="badge" style="background:#f3f4f6;color:#6b7280">n/a</span></td></tr>`;
          }
          const pass = val <= r.max;
          if (!pass) {
            if (r.group === "ro5") violations++;
            else veber++;
          }
          const shown = r.key === "MW" || r.key === "TPSA" ? val.toFixed(1) : val;
          return `<tr><td>${r.label}</td><td>${shown}</td><td>${r.limit}</td>
            <td>${pass
              ? '<span class="badge" style="background:#ecfdf5;color:#059669">pass</span>'
              : '<span class="badge" style="background:#fef2f2;color:#dc2626">fail</span>'}</td></tr>`;
        })
        .join("");

      let verdict, color;
      if (violations === 0) {
        verdict = "Compliant with Lipinski's rule of five";
        color = "#059669";
      } else if (violations === 1) {
        verdict = "One violation — usually still considered drug-like";
        color = "#d97706";
      } else {
        verdict = `${violations} violations — likely poor oral bioavailability`;
        color = "#dc2626";
      }
      const veberNote = veber
        ? `<div class="hint" style="color:#dc2626">${veber} Veber criterion(s) not met</div>`
        : '<div class="hint" style="color:#059669">Veber criteria satisfied</div>';

      html += `<div style="margin-bottom:18px">
        <div class="hint" style="margin-bottom:6px">Molecule ${idx + 1}: <code>${row.smiles}</code></div>
        <div style="font-weight:700;color:${color};margin-bottom:8px">${verdict}</div>
        <table>
          <tr><th>Rule</th><th>Value</th><th>Limit</th><th>Result</th></tr>
          ${body}
        </table>
        ${veberNote}
      </div>`;
    });

    $("#lip-result").style.display = "block";
    $("#lip-result").innerHTML = html;
    setStatus("#lip-status", "Done", "ok");
  }

  /* ── 页面：批量转换 ── */
  async function runBatch() {
    const data = $("#batch-input").value;
    if (!data.trim()) return setStatus("#batch-status", "Please enter molecule data", "err");
    const opts = $$(".chips input:checked").map((c) => c.value);
    setStatus("#batch-status", "Converting…", "");

    const out = $("#batch-out");
    const img = $("#batch-image");
    if (img) { img.style.display = "none"; img.innerHTML = ""; }

    const j = await postJSON("/api/batch", {
      data, from: $("#batch-from").value, to: $("#batch-to").value, opts,
    });
    if (!j.ok) {
      out.textContent = "";
      setStatus("#batch-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }

    if (j.binary) {
      out.textContent = "";
      out.style.display = "none";
      if (img) {
        img.style.display = "block";
        if (j.zip_url) {
          const tiles = (j.previews || []).map((u, i) =>
            `<figure style="margin:0;text-align:center"><img src="${u}" style="max-width:100%;height:auto" alt="molecule ${i + 1}"/><figcaption style="font-size:12px;color:var(--muted)">#${i + 1}</figcaption></figure>`
          ).join("");
          img.innerHTML =
            `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:14px">${tiles}</div>` +
            `<div style="text-align:center"><a class="btn" download="molecules.zip" href="${j.zip_url}">Download ZIP (${j.rendered} images)</a>` +
            (j.failed ? `<div class="hint" style="color:var(--err)">${j.failed} molecule(s) could not be rendered</div>` : "") +
            `</div>`;
        } else if ((j.mime || "").indexOf("image/") === 0) {
          img.innerHTML = '<img src="' + j.data_url + '" style="max-width:100%;height:auto" alt="converted" />';
        } else {
          const ext = (j.mime || "").split("/")[1] || "bin";
          const kb = Math.round((j.data_url || "").length * 0.75 / 1024);
          img.innerHTML =
            '<div style="text-align:center"><p style="color:var(--muted);font-size:14px">' + kb + ' KB· ' + (j.mime || "binary") + '</p>' +
            '<a class="btn" download="output.' + ext + '" href="' + j.data_url + '">Download</a></div>';
        }
      }
    } else {
      out.style.display = "";
      out.textContent = j.result || "";
    }
    setStatus("#batch-status", "Done · " + j.converted + " molecule(s) converted", "ok");
  }

  /* ── 页面：分子式 ── */
  function formulaMode() {
    const el = document.querySelector('input[name="fmode"]:checked');
    return el ? el.value : "formula";
  }

  async function runFormula() {
    const mode = formulaMode();
    setStatus("#f-status", "Calculating…", "");
    const result = $("#f-result");

    if (mode === "formula") {
      const formula = $("#f-formula").value.trim();
      if (!formula) return setStatus("#f-status", "Please enter a formula", "err");
      const j = await postJSON("/api/formula", { mode: "formula", formula });
      if (!j.ok) {
        setStatus("#f-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
        return;
      }
      const rows = (j.composition || [])
        .map((r) => `<tr><td>${r.element}</td><td>${r.count}</td><td>${r.mass.toFixed(3)}</td><td>${r.percent.toFixed(2)} %</td></tr>`)
        .join("");
      result.style.display = "block";
      result.innerHTML =
        `<label>Molecular formula</label><div class="metric">${j.formula}</div>` +
        `<div class="hint" style="margin-bottom:12px">${j.atoms} atoms in total</div>` +
        `<label>Molecular weight</label><div class="metric" style="margin-bottom:16px">${j.mw.toFixed(3)} g/mol</div>` +
        `<table><tr><th>Element</th><th>Atoms</th><th>Mass (g/mol)</th><th>Mass %</th></tr>${rows}</table>`;
      setStatus("#f-status", "Done", "ok");
      return;
    }

    const data = $("#f-input").value;
    if (!data.trim()) return setStatus("#f-status", "Please enter molecule data", "err");
    const j = await postJSON("/api/formula", {
      mode: "structure", data, from: $("#f-from").value,
    });
    if (!j.ok) {
      setStatus("#f-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }
    const rows = (j.rows || [])
      .map((r) => `<tr><td><code>${r.smiles}</code></td><td>${r.formula}</td><td>${r.mw !== null ? r.mw.toFixed(3) : "—"}</td></tr>`)
      .join("");
    result.style.display = "block";
    result.innerHTML =
      `<table><tr><th>SMILES</th><th>Formula</th><th>Molecular weight</th></tr>${rows}</table>`;
    setStatus("#f-status", "Done", "ok");
  }

  /* ── 页面：FASTA / FASTQ ── */
  async function runBio() {
    const tool = $("#bio-tool");
    if (!tool) return;
    const op = tool.dataset.op;
    const data = $("#bio-input").value;
    if (!data.trim()) return setStatus("#bio-status", "Please enter sequence data", "err");

    const body = { op, data };
    if (op === "translate") {
      const f = $("#bio-frame");
      body.frame = f ? parseInt(f.value, 10) || 0 : 0;
    }

    setStatus("#bio-status", "Working…", "");
    const j = await postJSON("/api/bio", body);
    if (!j.ok) {
      setStatus("#bio-status", j.error + (j.detail ? " — " + j.detail : ""), "err");
      return;
    }

    const statsBox = $("#bio-stats");
    const out = $("#bio-out");

    if (op === "stats") {
      const rows = (j.rows || [])
        .map((r) => `<tr><td>${r.header}</td><td>${r.length}</td><td>${r.gc_pct}%</td>` +
          `<td>${r.at_pct}%</td><td>${r.n_count}</td><td>${r.ambiguous}</td>` +
          `<td>${r.gc_skew}</td><td>${r.at_skew}</td></tr>`)
        .join("");
      statsBox.style.display = "block";
      statsBox.innerHTML =
        `<table><tr><th>Sequence</th><th>Length</th><th>GC %</th><th>AT %</th>` +
        `<th>N</th><th>Ambiguous</th><th>GC skew</th><th>AT skew</th></tr>${rows}</table>`;
      out.textContent = "";
      out.style.display = "none";
    } else {
      statsBox.style.display = "none";
      out.style.display = "";
      out.textContent = j.result || "";
    }

    const extra = j.count !== undefined ? " · " + j.count + " record(s)" : "";
    setStatus("#bio-status", "Done" + extra, "ok");
  }


  /* ── 页面：IUPAC 名称转结构 ── */
  async function resolveName(name) {
    // 1) OPSIN（服务端代理）
    try {
      const j = await postJSON("/api/iupac", { name });
      if (j && j.ok && j.resolved && j.smiles) {
        return { smiles: j.smiles, inchi: j.inchi, inchikey: j.inchikey, source: "OPSIN" };
      }
    } catch (e) { /* fall through */ }

    // 2) PubChem（浏览器直连，走 CORS）
    try {
      const url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/" +
        encodeURIComponent(name) +
        "/property/SMILES,ConnectivitySMILES,MolecularFormula,MolecularWeight,InChIKey/JSON";
      const resp = await fetch(url, { headers: { Accept: "application/json" } });
      if (resp.ok) {
        const d = await resp.json();
        const p = d && d.PropertyTable && d.PropertyTable.Properties && d.PropertyTable.Properties[0];
        if (p) {
          const smiles = p.SMILES || p.ConnectivitySMILES || p.IsomericSMILES || p.CanonicalSMILES || "";
          if (smiles) {
            return {
              smiles: smiles,
              formula: p.MolecularFormula || "",
              mw: p.MolecularWeight || null,
              inchikey: p.InChIKey || "",
              cid: p.CID || null,
              source: "PubChem",
            };
          }
        }
        return { error: "PubChem found no structure for this name", reason: "notfound" };
      }
      if (resp.status === 404) {
        return { error: "Not found in OPSIN or PubChem — check the spelling", reason: "notfound" };
      }
      return { error: "PubChem returned HTTP " + resp.status, reason: "network" };
    } catch (e) {
      return {
        error: "OPSIN could not parse this name and PubChem is unreachable from your browser",
        reason: "network",
      };
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function renderNameResult(name, r) {
    if (r.error) {
      return `<div class="hint"><strong>${escapeHtml(name)}</strong></div>` +
        `<div style="color:var(--err);font-size:14px;margin-top:6px">${r.error}</div>`;
    }
    const badge = `<span class="badge">${r.source}</span>`;
    const rows = [];
    rows.push(`<tr><th>SMILES</th><td><code>${escapeHtml(r.smiles)}</code></td></tr>`);
    if (r.inchi) rows.push(`<tr><th>InChI</th><td><code style="word-break:break-all">${escapeHtml(r.inchi)}</code></td></tr>`);
    if (r.inchikey) rows.push(`<tr><th>InChIKey</th><td><code>${escapeHtml(r.inchikey)}</code></td></tr>`);
    if (r.formula) rows.push(`<tr><th>Formula</th><td>${escapeHtml(r.formula)}</td></tr>`);
    if (r.mw) rows.push(`<tr><th>Molecular weight</th><td>${r.mw}</td></tr>`);
    if (r.cid) rows.push(`<tr><th>PubChem CID</th><td><a href="https://pubchem.ncbi.nlm.nih.gov/compound/${r.cid}" target="_blank" rel="noopener">${r.cid}</a></td></tr>`);
    return `<div class="row" style="margin-top:0;justify-content:space-between">
        <div style="font-weight:600">${escapeHtml(name)}</div>${badge}</div>
      <div style="overflow:auto;margin-top:10px"><table>${rows.join("")}</table></div>
      <div class="svg-slot" style="margin-top:12px"></div>`;
  }

  async function runIupac() {
    const names = $("#iupac-input").value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!names.length) return setStatus("#iupac-status", "Please enter an IUPAC name", "err");
    if (names.length > 20) return setStatus("#iupac-status", "Please use 20 names or fewer", "err");

    const box = $("#iupac-results");
    box.innerHTML = "";
    setStatus("#iupac-status", "Resolving…", "");

    let ok = 0;
    for (const name of names) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `<div class="hint">${escapeHtml(name)}</div><div class="hint">Resolving…</div>`;
      box.appendChild(card);

      const r = await resolveName(name);
      card.innerHTML = renderNameResult(name, r);

      if (r.smiles) {
        ok++;
        try {
          const j = await postJSON("/api/depict", { data: r.smiles, from: "smi" });
          if (j.ok) {
            const slot = card.querySelector(".svg-slot");
            const holder = document.createElement("div");
            holder.className = "svg-box";
            holder.innerHTML = j.svg;
            slot.appendChild(holder);
          }
        } catch (e) { /* ignore */ }
      }
    }

    const failed = names.length - ok;
    const msg = failed === 0
      ? `Done · all ${names.length} resolved`
      : `Done · ${ok} of ${names.length} resolved · ${failed} not found (see the cards below)`;
    setStatus("#iupac-status", msg, ok ? (failed ? "ok" : "ok") : "err");
  }

  /* ── 初始化 ── */
  function downloadBlob(content, type, name) {
    const blob = new Blob([content], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function init() {
    const page = document.body.dataset.page || "";
    bindExamples();
    bindFiles();
    bindCopy();
    loadFormats();

    if (page === "convert") {
      $("#conv-run").addEventListener("click", runConvert);
      $("#conv-toggle").addEventListener("click", () => {
        const pre = $("#conv-out");
        const preview = $("#conv-preview");
        const btn = $("#conv-toggle");
        const showingSource = pre.style.display !== "none";
        pre.style.display = showingSource ? "none" : "";
        preview.style.display = showingSource ? "grid" : "none";
        btn.textContent = showingSource ? "View preview" : "View source";
      });
      $("#conv-download").addEventListener("click", () => {
        if (convBinary) {
          const a = document.createElement("a");
          a.href = convBinary.dataUrl;
          a.download = "output." + convBinary.ext;
          a.click();
          return;
        }
        const text = $("#conv-out").textContent || "";
        if (!text) return;
        const ext = $("#conv-to").value === "svg" ? "svg" : "txt";
        downloadBlob(text, "text/plain;charset=utf-8", "output." + ext);
      });
      window.addEventListener("resize", () => { if (viewerConv) viewerConv.resize(); });
    }

    if (page === "properties") {
      $("#prop-run").addEventListener("click", runProps);
    }

    if (page === "depict") {
      $("#depict-run").addEventListener("click", runDepict);
      $("#depict-download").addEventListener("click", () => {
        if (!lastSvg) return;
        downloadBlob(lastSvg, "image/svg+xml", "molecule.svg");
      });
    }

    if (page === "3d") {
      $("#mol3d-run").addEventListener("click", runMol3d);
      $("#mol3d-style").addEventListener("change", () => {
        if (!viewer3d) return;
        applyStyle(viewer3d, $("#mol3d-style").value);
        viewer3d.render();
      });
      $("#mol3d-download").addEventListener("click", () => {
        if (!lastSdf) return;
        downloadBlob(lastSdf, "chemical/x-mdl-sdfile", "molecule.sdf");
      });
      window.addEventListener("resize", () => { if (viewer3d) viewer3d.resize(); });
    }

    if (page === "substructure") {
      $("#sub-run").addEventListener("click", runSub);
    }

    if (page === "similarity") {
      $("#sim-run").addEventListener("click", runSim);
    }

    if (page === "lipinski") {
      $("#lip-run").addEventListener("click", runLipinski);
    }

    if (page === "batch") {
      $("#batch-run").addEventListener("click", runBatch);
      $("#batch-download").addEventListener("click", () => {
        const text = $("#batch-out").textContent || "";
        if (!text) return;
        downloadBlob(text, "text/plain;charset=utf-8", "converted." + ($("#batch-to").value || "txt"));
      });
    }

    if (page === "formula") {
      $("#f-run").addEventListener("click", runFormula);
      $$('input[name="fmode"]').forEach((radio) => {
        radio.addEventListener("change", () => {
          const m = formulaMode();
          $("#f-formula-block").style.display = m === "formula" ? "" : "none";
          $("#f-structure-block").style.display = m === "structure" ? "" : "none";
        });
      });
    }

    if (page === "iupac") {
      $("#iupac-run").addEventListener("click", runIupac);
    }

    if (page === "bio") {
      $("#bio-run").addEventListener("click", runBio);
      $("#bio-download").addEventListener("click", () => {
        const text = $("#bio-out").textContent || "";
        if (!text) return;
        downloadBlob(text, "text/plain;charset=utf-8", "output.txt");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
