/* WRFT 2023 website: calendar, day explorer, impact chart, dog quadrant, line-up builder, dog table.
   All data comes from assets/data.js (window.WRFT), written by flyball/report/site.py. */
(function () {
  "use strict";
  const D = window.WRFT;
  const C = { wrft: "#6250d6", wrftLight: "#c9c2f2", field: "#898781", fieldLight: "#c3c2b7", good: "#1baf7a",
              fault: "#eb6834", mid: "#f0efec", ink: "#0b0b0b", ink2: "#52514e", grid: "#e1e0d9", surface: "#fcfcfb" };

  // ---- Hungarian number formatting ---------------------------------------------------------
  const MINUS = "−";
  function num(x, dec, sign) {
    if (x === null || x === undefined || Number.isNaN(x)) return "–";
    const s = Math.abs(x).toFixed(dec).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    if (Number(Math.abs(x).toFixed(dec)) === 0) return sign ? "±" + s : s;
    return x < 0 ? MINUS + s : (sign ? "+" + s : s);
  }
  const pct = (x, dec = 0, sign = false) => (x === null || x === undefined) ? "–" : num(100 * x, dec, sign) + "%";
  const sec = (x, dec = 2, sign = false) => (x === null || x === undefined) ? "–" : num(x, dec, sign) + " mp";

  function el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v; else if (k === "style") e.style.cssText = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
    }
    for (const c of children) if (c !== null && c !== undefined) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
    return e;
  }

  // ---- Colour scale for the calendar (diverging orange - grey - aqua around the field) ---------------
  function hexToRgb(h) { return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); }
  function mix(a, b, t) { const x = hexToRgb(a), y = hexToRgb(b); return x.map((v, i) => Math.round(v + (y[i] - v) * t)); }
  function divColor(v) {             // v in [-1, 1]
    const rgb = v < 0 ? mix(C.mid, C.fault, -v) : mix(C.mid, C.good, v);
    const lum = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
    return { bg: `rgb(${rgb.join(",")})`, fg: lum < 0.5 ? "#fff" : C.ink };
  }

  // ---- Season calendar ------------------------------------------------------------------------
  function calendar() {
    const root = document.getElementById("calendar");
    if (!root) return;
    const events = [];
    for (const d of D.days) {
      let ev = events.find(e => e.event === d.event);
      if (!ev) { ev = { event: d.event, date: d.date, days: [] }; events.push(ev); }
      ev.days.push(d);
    }
    for (const ev of events) {
      const box = el("div", { class: "cal-event" }, el("div", { class: "cal-name" }, ev.event),
                     el("div", { class: "cal-date" }, ev.days[0].date_hu));
      const row = el("div", { class: "cal-days" });
      for (const d of ev.days) {
        const col = divColor(Math.max(-1, Math.min(1, (d.clean - D.field_clean) / 0.25)));
        const b = el("button", { class: "cal-tile", style: `background:${col.bg};color:${col.fg}`, "data-id": d.id,
                                 "aria-label": `${d.event}, ${d.weekday}: hibátlan futam ${pct(d.clean)}, győzelem ${pct(d.win)}` },
          el("div", { class: "d" }, d.weekday.slice(0, 3)), el("div", { class: "c" }, pct(d.clean)),
          el("div", { class: "w" }, "nyert " + pct(d.win)), el("div", { class: "t" }, num(d.temp, 0) + " °C"));
        if (d.below) b.append(el("span", { class: "below", title: "kevesebb győzelem, mint a divízió többi csapatáé" }, "▲"));
        b.addEventListener("click", () => { selectDay(d.id); document.getElementById("versenynapok").scrollIntoView(); });
        row.append(b);
      }
      box.append(row);
      root.append(box);
    }
  }

  // ---- Day explorer ------------------------------------------------------------------------------
  function dayPicker() {
    const root = document.getElementById("day-picker");
    if (!root) return;
    for (const d of D.days) {
      const b = el("button", { role: "tab", "aria-selected": "false", "data-id": d.id },
                   `${d.event} · ${d.weekday.slice(0, 3)}`);
      if (d.below) b.append(el("span", { class: "b" }, " ▲"));
      b.addEventListener("click", () => selectDay(d.id));
      root.append(b);
    }
    selectDay(D.days[0].id);
  }

  function selectDay(id) {
    const d = D.days.find(x => x.id === id);
    if (!d) return;
    document.querySelectorAll("#day-picker button").forEach(b => b.setAttribute("aria-selected", String(b.dataset.id === id)));
    document.querySelectorAll(".cal-tile").forEach(b => b.classList.toggle("selected", b.dataset.id === id));
    const root = document.getElementById("day-detail");
    root.replaceChildren();
    root.append(el("p", { class: "day-title" }, `${d.competition} – ${d.date_hu}, ${d.weekday} (${d.venue})`));
    if (d.below) root.append(el("p", { class: "flag" }, `▲ Ezen a napon a WRFT kevesebb futamot nyert, mint a divízió többi csapata (${num(100 * d.peer_win_gap, 0, true)} százalékpont).`));
    const kpi = (label, value, small) => el("div", { class: "kpi" }, el("dt", {}, label), el("dd", {}, value, small ? el("small", {}, " " + small) : null));
    root.append(el("dl", { class: "kpis" },
      kpi("Futamok", num(d.heats, 0)),
      kpi("Győzelem", pct(d.win), `(${pct(d.win_lo)}–${pct(d.win_hi)})`),
      kpi("Hibátlan futam", pct(d.clean), `mezőnyátlag: ${pct(D.field_clean)}`),
      kpi("Korai rajt", pct(d.fs), "a futamokban"), kpi("Korai váltás", pct(d.pf), "a futamokban"), kpi("Futási hiba", pct(d.rf), "a futamokban"),
      kpi("Elkerülhető vereség", pct(d.avoidable), "a vereségekből"),
      kpi("Sebesség", num(d.speed_wrft, 1, true) + "%", "a kutyák átlagos napjához képest (− = gyorsabb)"),
      kpi("Hőmérséklet", num(d.temp, 0) + " °C", "max. " + num(d.temp_max, 0) + " °C"),
      kpi("Páratartalom", num(d.humidity, 0) + "%"), kpi("Szél", num(d.wind, 1) + " m/s", "lökés " + num(d.gust, 0)),
      kpi("Eső", num(d.rain, 1) + " mm", "előző 24 óra: " + num(d.rain_before, 1))));
    const cols = ["Csapat", "Futam", "Győzelem", "Hibátlan futam", "Jellemző tiszta idő", "Legjobb tiszta idő", "Korai rajt", "Korai váltás", "Futási hiba", "Jellemző futás"];
    const t = el("table", { class: "data" }, el("thead", {}, el("tr", {}, ...cols.map((c, i) => el("th", { class: i ? "r" : "l" }, c)))));
    const tb = el("tbody");
    for (const x of d.teams) {
      tb.append(el("tr", {}, el("td", {}, x.team), el("td", { class: "r" }, num(x.heats, 0)), el("td", { class: "r" }, pct(x.win)),
        el("td", { class: "r" }, pct(x.clean)), el("td", { class: "r" }, sec(x.clean_time)), el("td", { class: "r" }, sec(x.best)),
        el("td", { class: "r" }, pct(x.fs)), el("td", { class: "r" }, pct(x.pf)), el("td", { class: "r" }, pct(x.rf)),
        el("td", { class: "r" }, sec(x.run))));
    }
    t.append(tb);
    root.append(el("div", { class: "table-scroll" }, t),
      el("p", { class: "footnote" }, "Hibák: a csapat futamainak hány százalékában fordultak elő. Sebesség: ugyanazok a kutyák a saját átlagos napjukhoz képest."));
  }

  // ---- Vega charts --------------------------------------------------------------------------------
  const vegaOpts = {
    actions: false, renderer: "svg",
    formatLocale: { decimal: ",", thousands: " ", grouping: [3], currency: ["", ""] },
    config: {
      font: "Source Sans 3, system-ui, sans-serif", background: C.surface, view: { stroke: null },
      axis: { labelColor: C.ink2, titleColor: C.ink2, gridColor: C.grid, domainColor: C.fieldLight, tickColor: C.fieldLight,
              labelFontSize: 13, titleFontSize: 13, titleFontWeight: 400 },
      legend: { labelColor: C.ink2, titleColor: C.ink2, labelFontSize: 13, titleFontSize: 13, orient: "bottom" },
    },
  };

  function ledgerChart() {
    const target = document.getElementById("ledger-chart");
    if (!target || !window.vegaEmbed) return;
    const rows = D.ledger_main.map((r, i) => ({ ...r, i, shown: Math.min(r.wins, 70), lbl: (r.sub ? "   " : "") + r.label,
      txt: r.group === "Nem számít" ? "0 (nem számít)" : `+${num(r.wins, 0)} (${num(r.lo, 0)}–${num(r.hi, 0)})`,
      kind: r.group === "Viszonyítás" ? "ref" : (r.group === "Nem számít" ? "zero" : (r.sub ? "sub" : "main")) }));
    const order = rows.map(r => r.lbl);
    // Reserve a fixed label column: Vega measures the labels before the web font loads and under-reserves.
    const labelW = target.clientWidth < 640 ? 150 : 290;
    const spec = {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json", width: Math.max(160, target.clientWidth - labelW - 40),
      height: rows.length * 30, data: { values: rows },
      encoding: { y: { field: "lbl", type: "nominal", sort: order, title: null, scale: { paddingInner: 0.35 },
                       axis: { labelLimit: labelW, minExtent: labelW, maxExtent: labelW + 12, labelFontSize: target.clientWidth < 640 ? 12 : 14 } } },
      layer: [
        { mark: { type: "bar", clip: true },   // cornerRadiusEnd mis-places bars in vega 5.30 (svg)
          encoding: {
            x: { field: "shown", type: "quantitative", title: "plusz győzelem szezononként (futam)", scale: { domain: [0, 70] } },
            color: { field: "kind", type: "nominal", legend: null,
                     scale: { domain: ["ref", "main", "sub", "zero"], range: [C.grid, C.wrft, C.wrftLight, C.field] } },
            tooltip: [{ field: "label", title: "Lehetőség" }, { field: "group", title: "Mi kell hozzá" },
                      { field: "wins", title: "Plusz győzelem", format: ",.1f" },
                      { field: "lo", title: "Legalább", format: ",.1f" }, { field: "hi", title: "Legfeljebb", format: ",.1f" }] } },
        { mark: { type: "rule", color: C.ink2, clip: true }, transform: [{ filter: "datum.kind !== 'ref' && datum.hi > 0" }],
          encoding: { x: { field: "lo", type: "quantitative" }, x2: { field: "hi" } } },
        { mark: { type: "text", align: "left", dx: 6, fontSize: 13, color: C.ink },
          transform: [{ calculate: "datum.kind === 'ref' ? 40 : max(datum.hi, datum.wins)", as: "tx" }],
          encoding: { x: { field: "tx", type: "quantitative" }, text: { field: "txt" } } },
      ],
    };
    vegaEmbed(target, spec, vegaOpts).catch(console.error);
  }

  function ledgerTable() {
    const root = document.getElementById("ledger-table");
    if (!root) return;
    const t = el("table", { class: "data" }, el("thead", {}, el("tr", {},
      el("th", {}, "Lehetőség"), el("th", {}, "Típus"), el("th", { class: "r" }, "Plusz győzelem"), el("th", { class: "r" }, "Bizonytalansági tartomány"),
      el("th", { class: "r" }, "Győzelmi arány változása (százalékpont)"))));
    const tb = el("tbody");
    for (const r of D.ledger_all) {
      tb.append(el("tr", {}, el("td", {}, r.label), el("td", {}, r.group), el("td", { class: "r" }, "+" + num(r.wins, 1)),
        el("td", { class: "r" }, `${num(r.lo, 1)}–${num(r.hi, 1)}`), el("td", { class: "r" }, num(r.pp, 1, true))));
    }
    t.append(tb);
    root.append(el("div", { class: "table-scroll" }, t));
  }

  function quadrantChart() {
    const target = document.getElementById("quadrant-chart");
    if (!target || !window.vegaEmbed) return;
    const rows = D.dogs.filter(d => d.runs >= D.pool_min_runs).map(d => ({ ...d, anyp: 100 * d.any,
      role: D.a_team.includes(d.dog) ? "a legjobb négyes tagja" : (D.quadrant_targets.includes(d.dog) ? "edzéssel javítandó" : "többi kutya"),
      fs_t: d.fs === null ? "–" : pct(d.fs), ep_t: d.ep === null ? "–" : pct(d.ep), rf_t: pct(d.rf, 1) }));
    const named = rows.filter(r => r.role !== "többi kutya");
    const spec = {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json", width: Math.max(220, target.clientWidth - 70), height: 400,
      layer: [
        { data: { values: rows }, mark: { type: "point", filled: true, stroke: C.surface, strokeWidth: 2, opacity: 0.95 },
          encoding: {
            x: { field: "median_run", type: "quantitative", scale: { reverse: true, zero: false }, title: "jellemző futási idő (mp) → gyorsabb", axis: { format: ",.1f" } },
            y: { field: "anyp", type: "quantitative", title: "hibaarány rajtban, váltásban, futásban (%)", scale: { zero: false }, axis: { format: ",.0f" } },
            size: { field: "runs", type: "quantitative", legend: null, scale: { range: [40, 420] } },
            color: { field: "role", type: "nominal", title: null,
                     scale: { domain: ["edzéssel javítandó", "a legjobb négyes tagja", "többi kutya"], range: [C.fault, C.wrft, C.fieldLight] } },
            order: { field: "role", sort: "descending" },
            tooltip: [{ field: "dog", title: "Kutya" }, { field: "category", title: "Nem, ivarállapot" },
                      { field: "median_run", title: "Jellemző futás (mp)", format: ",.2f" }, { field: "runs", title: "Értékelhető futás" },
                      { field: "fs_t", title: "Korai rajt" }, { field: "ep_t", title: "Korai váltás" }, { field: "rf_t", title: "Futási hiba" }] } },
        { data: { values: named }, mark: { type: "text", dx: 8, dy: -8, align: "left", fontSize: 13, color: C.ink },
          encoding: { x: { field: "median_run", type: "quantitative" }, y: { field: "anyp", type: "quantitative" }, text: { field: "dog" } } },
      ],
    };
    vegaEmbed(target, spec, vegaOpts).catch(console.error);
  }

  // ---- Line-up builder (scoring lives in lineup.js) ---------------------------------------------------
  const M = D.model;
  const { score, bestOrder } = window.WRFTLineup.make(M);
  const byName = Object.fromEntries(M.dogs.map((d, i) => [d.name, i]));

  function builder() {
    const slots = document.getElementById("slots");
    if (!slots) return;
    const sorted = M.dogs.map(d => d.name).sort((a, b) => a.localeCompare(b, "hu"));
    const roles = ["1. kutya (rajtoló)", "2. kutya", "3. kutya", "4. kutya"];
    const selects = roles.map((r, i) => {
      const s = el("select", { id: "slot" + i });
      for (const n of sorted) s.append(el("option", { value: n }, n));
      const meta = el("div", { class: "meta" });
      slots.append(el("div", { class: "slot" }, el("label", { for: "slot" + i }, r, s), meta));
      s.addEventListener("change", update);
      return { s, meta };
    });
    const preset = document.getElementById("preset");
    D.presets.forEach((p, i) => preset.append(el("option", { value: String(i) }, `${p.label}: ${p.dogs.join(" › ")}`)));
    preset.addEventListener("change", () => setDogs(D.presets[Number(preset.value)].dogs));
    document.getElementById("best-order").addEventListener("click", () => setDogs(bestOrder(selects.map(x => x.s.value))));
    const ref = score(D.a_team);

    function setDogs(names) { names.forEach((n, i) => { selects[i].s.value = n; }); update(); }

    function update() {
      const names = selects.map(x => x.s.value);
      const warn = document.getElementById("res-warn");
      selects.forEach(({ meta }, i) => {
        const d = M.dogs[byName[names[i]]];
        meta.textContent = i === 0
          ? `rajt ${sec(d.start_any)} · korai rajt ${pct(d.fs)} · ${num(d.starts, 0)} rajt`
          : `váltás ${sec(d.pass)} · korai váltás ${pct(d.ep)} · ${num(d.height, 1).replace(",0", "")} cm`;
      });
      if (new Set(names).size < 4) {
        warn.hidden = false; warn.textContent = "Minden kutya csak egyszer szerepelhet a csapatban.";
        document.getElementById("res-expected").textContent = "–";
        return;
      }
      const s = score(names);
      document.getElementById("res-expected").textContent = sec(s.expected);
      const delta = s.expected - ref.expected;
      const dEl = document.getElementById("res-delta");
      dEl.textContent = Math.abs(delta) < 0.005 ? "Ez a legjobb négyes." :
        `${num(delta, 2, true)} mp a legjobb négyeshez (${sec(ref.expected)}) képest`;
      dEl.className = "res-sub " + (delta < -0.005 ? "better" : (delta > 0.005 ? "worse" : ""));
      const bar = document.getElementById("res-bar");
      bar.replaceChildren();
      const total = 32;
      for (const [cls, v, label] of [["start", s.start, "rajt"], ["runs", s.runs, "négy futás"], ["pass", s.passes, "három váltás"], ["fault", s.fault, "várható hibaköltség"]]) {
        bar.append(el("div", { class: cls, style: `width:${(100 * v / total).toFixed(2)}%`, title: `${label}: ${sec(v)}` }));
      }
      document.getElementById("res-nofault").textContent = sec(s.noFault);
      document.getElementById("res-clean").textContent = pct(s.pClean);
      document.getElementById("res-hurdle").textContent = num(s.hurdle, 1).replace(",0", "") + " cm";
      document.getElementById("res-nf").textContent = num(s.nf, 2);
      if (!s.starterOk) {
        warn.hidden = false;
        warn.textContent = `${names[0]} keveset rajtolt (${num(M.dogs[byName[names[0]]].starts, 0)}-szor), ezért a rajtideje és a korai rajtjainak aránya csak bizonytalan becslés. „A legjobb sorrend” gomb csak megbízható rajtolót tesz az első helyre.`;
      } else { warn.hidden = true; }
    }
    setDogs(D.presets[0].dogs);
  }

  // ---- Dog table ------------------------------------------------------------------------------------
  function dogTable() {
    const table = document.getElementById("dog-table");
    if (!table) return;
    const cols = [
      ["dog", "Kutya", "l", d => d.dog], ["category", "Nem, ivarállapot", "l", d => d.category], ["breed", "Fajta", "l", d => d.breed],
      ["runs", "Értékelhető futás", "r", d => num(d.runs, 0)], ["competitions", "Verseny", "r", d => num(d.competitions, 0)],
      ["median_run", "Jellemző futás", "r", d => sec(d.median_run)], ["adj_run", "Összevethető futás", "r", d => sec(d.adj_run)],
      ["hurdle", "Akadály (cm)", "r", d => num(d.hurdle, 1).replace(",0", "")],
      ["starts", "Rajt", "r", d => num(d.starts, 0)], ["fs", "Korai rajt*", "r", d => d.fs === null ? "–" : pct(d.fs)],
      ["passes", "Váltás", "r", d => num(d.passes, 0)], ["median_pass", "Jellemző váltás", "r", d => d.median_pass === null ? "–" : sec(d.median_pass)],
      ["ep", "Korai váltás*", "r", d => d.ep === null ? "–" : pct(d.ep)], ["rf", "Futási hiba*", "r", d => pct(d.rf, 1)],
    ];
    let sortKey = "adj_run", dir = 1, query = "";
    const thead = el("thead"), tbody = el("tbody");
    const tr = el("tr");
    cols.forEach(([key, label, align]) => {
      const th = el("th", { class: align, scope: "col", tabindex: "0" }, label);
      const go = () => { dir = sortKey === key ? -dir : 1; sortKey = key; render(); };
      th.addEventListener("click", go);
      th.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      th.dataset.key = key;
      tr.append(th);
    });
    thead.append(tr);
    table.append(thead, tbody);
    document.getElementById("dog-search").addEventListener("input", e => { query = e.target.value.toLowerCase(); render(); });

    function render() {
      const rows = D.dogs.filter(d => !query || `${d.dog} ${d.category} ${d.breed}`.toLowerCase().includes(query))
        .sort((a, b) => {
          const x = a[sortKey], y = b[sortKey];
          if (x === null) return 1; if (y === null) return -1;
          return (typeof x === "string" ? x.localeCompare(y, "hu") : x - y) * dir;
        });
      tbody.replaceChildren(...rows.map(d => {
        const r = el("tr", D.a_team.includes(d.dog) ? { class: "ateam" } : {});
        cols.forEach(([, , align, f]) => r.append(el("td", { class: align }, f(d))));
        return r;
      }));
      thead.querySelectorAll("th").forEach(th => {
        if (th.dataset.key === sortKey) th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        else th.removeAttribute("aria-sort");
      });
      document.getElementById("dog-count").textContent = `${rows.length} kutya`;
    }
    render();
  }

  calendar();
  dayPicker();
  ledgerChart();
  ledgerTable();
  quadrantChart();
  builder();
  dogTable();
})();
