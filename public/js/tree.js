/* ============================================================
   Quesenberry & Harvey — interactive tree
   Three views (Pedigree / Timeline / Map) sharing one focus state.
   ============================================================ */

(function () {
  "use strict";

  // ----- shared state -----
  const state = {
    people: [],
    byId: new Map(),
    view: "pedigree",
    focusedId: null,
  };

  const branchColor = (branch) => ({
    quesenberry: "var(--rust)",
    harvey:      "var(--forest)",
    carmichael:  "var(--gold-leaf)",
  }[branch] || "var(--ink-soft)");

  const branchHex = (branch) => ({
    quesenberry: "#7a4a1f",
    harvey:      "#3a5a3e",
    carmichael:  "#8a6d28",
  }[branch] || "#4a3520");

  // ----- bootstrap -----
  fetch("/tree.json")
    .then((r) => r.json())
    .then((data) => {
      state.people = data.people;
      state.people.forEach((p) => state.byId.set(p.id, p));
      // default focus: Lonnie (or first person)
      state.focusedId =
        (state.byId.has("lonnie-quesenberry") ? "lonnie-quesenberry"
         : state.people[0]?.id) || null;
      initControls();
      drawAll();
      renderSidePanel();
    })
    .catch((e) => {
      document.getElementById("view-pedigree").innerHTML =
        "<p style='padding:2rem; color:var(--rust);'>Could not load tree data: " + e + "</p>";
    });

  // ----- controls (tabs + search) -----
  function initControls() {
    document.querySelectorAll(".view-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const v = btn.dataset.view;
        state.view = v;
        document.querySelectorAll(".view-tab").forEach((b) => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-selected", b === btn ? "true" : "false");
        });
        document.querySelectorAll(".view").forEach((el) => {
          el.classList.toggle("active", el.id === "view-" + v);
        });
        // map needs to recompute size when revealed
        if (v === "map" && state._leafletMap) {
          setTimeout(() => state._leafletMap.invalidateSize(), 50);
        }
      });
    });

    const input = document.getElementById("search");
    const results = document.getElementById("search-results");
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      if (!q) { results.hidden = true; results.innerHTML = ""; return; }
      const matches = state.people
        .filter((p) => p.name.toLowerCase().includes(q))
        .slice(0, 8);
      results.innerHTML = matches.map((p) =>
        `<li data-id="${p.id}"><span class="nm">${p.name}</span> <span class="ls">${p.lifespan}</span></li>`
      ).join("");
      results.hidden = matches.length === 0;
    });
    results.addEventListener("click", (e) => {
      const li = e.target.closest("li[data-id]");
      if (!li) return;
      focusOn(li.dataset.id);
      input.value = "";
      results.hidden = true;
    });
    input.addEventListener("blur", () => {
      setTimeout(() => { results.hidden = true; }, 150);
    });
  }

  // ----- focus & side panel -----
  function focusOn(id) {
    if (!state.byId.has(id)) return;
    state.focusedId = id;
    drawAll();
    renderSidePanel();
  }

  function renderSidePanel() {
    const panel = document.getElementById("side-panel");
    const p = state.byId.get(state.focusedId);
    if (!p) {
      panel.innerHTML = "<p class='muted'>Click any name to focus on a person.</p>";
      return;
    }
    const facts = [];
    if (p.birth)      facts.push(["Born", `${p.birth}${p.birthPlace ? ", " + p.birthPlace : ""}`]);
    if (p.death)      facts.push(["Died", `${p.death}${p.deathPlace ? ", " + p.deathPlace : ""}`]);
    if (p.burial)     facts.push(["Buried", p.burial]);
    if (p.father)     facts.push(["Father", linkName(p.father)]);
    if (p.mother)     facts.push(["Mother", linkName(p.mother)]);
    if (p.spouse)     facts.push(["Spouse", linkName(p.spouse)]);
    if (p.children?.length) facts.push(["Children", p.children.map(linkName).join("<br>")]);
    if (p.military)   facts.push(["Military", p.military]);
    const verifyDot = {
      documented: ["#3a5a3e", "Documented"],
      partial:    ["#8a6d28", "Partially documented"],
      tradition:  ["#7a4a1f", "Family tradition"],
    }[p.verified] || ["#4a3520", "Not yet documented"];

    panel.innerHTML = `
      <div class="panel-head" style="border-left: 4px solid ${branchHex(p.branch)};">
        <p class="panel-eyebrow">${p.branch?.toUpperCase() || ""} LINE · GEN ${p.generation ?? "?"}</p>
        <h3 class="panel-name">${p.name}</h3>
        <p class="panel-lifespan">${p.lifespan || ""}</p>
        <p class="panel-stamp"><span class="dot" style="background:${verifyDot[0]}"></span>${verifyDot[1]}</p>
      </div>
      ${p.epitaph ? `<p class="panel-epitaph"><em>${p.epitaph}</em></p>` : ""}
      <dl class="panel-facts">
        ${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}
      </dl>
      <a class="panel-link" href="/people/${p.id}.html">Read full profile →</a>
    `;
  }

  function linkName(id) {
    const p = state.byId.get(id);
    if (!p) {
      const humanized = id.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
      return `<span class="person-stub" title="No record yet">${humanized}</span>`;
    }
    return `<a href="#" data-focus="${id}">${p.name}</a>`;
  }

  // delegate clicks on panel-internal data-focus links
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-focus]");
    if (a) {
      e.preventDefault();
      focusOn(a.dataset.focus);
    }
  });

  // ----- draw all views -----
  function drawAll() {
    drawPedigree();
    drawTimeline();
    drawMap();
  }

  // ============================================================
  //   VIEW 1 — Pedigree (D3 hierarchy, flowing top-down)
  // ============================================================
  function drawPedigree() {
    const container = document.getElementById("view-pedigree");
    container.innerHTML = "";

    const root = state.byId.get("lonnie-quesenberry");
    if (!root) return;

    // Build a hierarchy by walking parents. Root is Lonnie+Ruth as a "couple" node.
    function build(personId, depth) {
      const p = state.byId.get(personId);
      if (!p || depth > 8) return null;
      const node = { id: p.id, person: p, children: [] };
      if (p.father && state.byId.has(p.father)) {
        const f = build(p.father, depth + 1);
        if (f) node.children.push(f);
      }
      if (p.mother && state.byId.has(p.mother)) {
        const m = build(p.mother, depth + 1);
        if (m) node.children.push(m);
      }
      return node;
    }

    // Two roots side by side: Lonnie's tree and Ruth's tree
    const lonnieTree = build("lonnie-quesenberry", 0);
    const ruthTree = build("ruth-harvey", 0);
    const data = {
      id: "__couple__",
      person: { name: "Lonnie & Ruth", branch: "" },
      children: [lonnieTree, ruthTree].filter(Boolean),
    };

    const w = container.clientWidth || 900;
    const h = 720;
    const margin = { top: 70, right: 30, bottom: 30, left: 30 };

    const svg = d3.select(container).append("svg")
      .attr("viewBox", `0 0 ${w} ${h}`)
      .style("width", "100%")
      .style("height", h + "px");

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const root2 = d3.hierarchy(data);
    const layout = d3.tree().size([w - margin.left - margin.right, h - margin.top - margin.bottom]);
    layout(root2);

    // links (skip the synthetic couple-root → real-person edges; draw spouse line instead)
    const realLinks = root2.links().filter(l => l.source.data.id !== "__couple__");
    g.selectAll("path.link")
      .data(realLinks)
      .enter()
      .append("path")
      .attr("class", "ped-link")
      .attr("fill", "none")
      .attr("stroke", "#b89b6f")
      .attr("stroke-width", 1.4)
      .attr("d", (d) => {
        const sx = d.source.x, sy = d.source.y;
        const tx = d.target.x, ty = d.target.y;
        const my = (sy + ty) / 2;
        return `M${sx},${sy} C${sx},${my} ${tx},${my} ${tx},${ty}`;
      });

    // Spouse line between Lonnie & Ruth
    if (root2.children?.length === 2) {
      const a = root2.children[0], b = root2.children[1];
      g.append("line")
        .attr("x1", a.x).attr("y1", a.y)
        .attr("x2", b.x).attr("y2", b.y)
        .attr("stroke", "#a83a1f").attr("stroke-width", 2).attr("stroke-dasharray", "4 3");
    }

    // nodes (only real people)
    const nodes = root2.descendants().filter((d) => d.data.id !== "__couple__");
    const node = g.selectAll("g.node")
      .data(nodes)
      .enter()
      .append("g")
      .attr("class", "ped-node")
      .attr("transform", (d) => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer")
      .on("click", (e, d) => focusOn(d.data.id))
      .on("mouseenter", function () { d3.select(this).select("rect").attr("stroke-width", 2.5); })
      .on("mouseleave", function () { d3.select(this).select("rect").attr("stroke-width", 1.2); });

    node.append("rect")
      .attr("x", -90).attr("y", -22)
      .attr("width", 180).attr("height", 44)
      .attr("fill", "#efe2c4")
      .attr("stroke", (d) => branchHex(d.data.person.branch))
      .attr("stroke-width", (d) => d.data.id === state.focusedId ? 3.5 : 1.2)
      .attr("rx", 1);

    node.append("text")
      .attr("text-anchor", "middle").attr("y", -4)
      .style("font-family", "'Playfair Display', Georgia, serif")
      .style("font-style", "italic").style("font-size", "12px").style("fill", "#2b1d10")
      .text((d) => truncate(d.data.person.name, 26));

    node.append("text")
      .attr("text-anchor", "middle").attr("y", 12)
      .style("font-family", "'Cormorant SC', Georgia, serif")
      .style("font-size", "10px").style("letter-spacing", "0.08em").style("fill", "#7a4a1f")
      .text((d) => d.data.person.lifespan || "");
  }

  // ============================================================
  //   VIEW 2 — Timeline (each person as a horizontal bar)
  // ============================================================
  function drawTimeline() {
    const container = document.getElementById("view-timeline");
    container.innerHTML = "";

    // Only people with at least a birth year
    const people = state.people
      .filter((p) => p.birthYear)
      .map((p) => ({
        ...p,
        _by: p.birthYear,
        _dy: p.deathYear || p.birthYear + 70, // estimate
      }))
      .sort((a, b) => a._by - b._by);

    if (!people.length) return;

    const minYear = Math.min(...people.map((p) => p._by));
    const maxYear = Math.max(...people.map((p) => p._dy));

    const w = container.clientWidth || 900;
    const rowH = 26;
    const h = people.length * rowH + 80;
    const margin = { top: 40, right: 30, bottom: 30, left: 220 };

    const svg = d3.select(container).append("svg")
      .attr("viewBox", `0 0 ${w} ${h}`)
      .style("width", "100%")
      .style("height", h + "px");

    const defs = svg.append("defs");
    const pat = defs.append("pattern")
      .attr("id", "diag")
      .attr("patternUnits", "userSpaceOnUse")
      .attr("width", 6).attr("height", 6)
      .attr("patternTransform", "rotate(45)");
    pat.append("rect").attr("width", 6).attr("height", 6).attr("fill", "#efe2c4");
    pat.append("line")
      .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6)
      .attr("stroke", "#7a4a1f").attr("stroke-width", 2);

    const x = d3.scaleLinear()
      .domain([minYear - 10, maxYear + 10])
      .range([margin.left, w - margin.right]);

    // x-axis with year ticks
    const xAxis = d3.axisTop(x).ticks(8).tickFormat(d3.format("d"));
    const axisG = svg.append("g")
      .attr("transform", `translate(0,${margin.top - 6})`)
      .call(xAxis);
    axisG.selectAll("text")
      .style("font-family", "'Cormorant SC', Georgia, serif")
      .style("letter-spacing", "0.12em")
      .style("fill", "#7a4a1f");
    axisG.selectAll("path, line").style("stroke", "#b89b6f");

    // Big-history shaded bands
    const eras = [
      [1607, 1776, "Colonial America"],
      [1776, 1865, "Republic & Civil War"],
      [1865, 1945, "Industrial → World Wars"],
      [1945, 2026, "Postwar America"],
    ];
    svg.append("g").selectAll("rect.era")
      .data(eras).enter()
      .append("rect")
      .attr("x", (d) => x(d[0]))
      .attr("y", margin.top)
      .attr("width", (d) => Math.max(0, x(d[1]) - x(d[0])))
      .attr("height", h - margin.top - margin.bottom)
      .attr("fill", (d, i) => i % 2 === 0 ? "rgba(184,155,111,0.10)" : "rgba(184,155,111,0.04)");

    // rows
    const rows = svg.append("g").selectAll("g.row")
      .data(people).enter()
      .append("g")
      .attr("class", "tl-row")
      .attr("transform", (_, i) => `translate(0,${margin.top + i * rowH + 16})`)
      .style("cursor", "pointer")
      .on("click", (e, d) => focusOn(d.id));

    // name label
    rows.append("text")
      .attr("x", margin.left - 10).attr("y", 4)
      .attr("text-anchor", "end")
      .style("font-family", "'Playfair Display', Georgia, serif")
      .style("font-style", "italic").style("font-size", "11px")
      .style("fill", (d) => d.id === state.focusedId ? "#a83a1f" : "#2b1d10")
      .style("font-weight", (d) => d.id === state.focusedId ? "700" : "400")
      .text((d) => truncate(d.name, 28));

    // life bar
    rows.append("rect")
      .attr("x", (d) => x(d._by))
      .attr("y", -7)
      .attr("width", (d) => Math.max(2, x(d._dy) - x(d._by)))
      .attr("height", 14)
      .attr("fill", (d) => branchHex(d.branch))
      .attr("opacity", (d) => d.id === state.focusedId ? 1 : 0.65)
      .attr("stroke", (d) => d.id === state.focusedId ? "#a83a1f" : "none")
      .attr("stroke-width", 2);

    // estimate marker (dashed end if no death year)
    rows.filter((d) => !d.deathYear)
      .append("rect")
      .attr("x", (d) => x(d._dy) - 8)
      .attr("y", -7).attr("width", 8).attr("height", 14)
      .attr("fill", "url(#diag)").attr("opacity", 0.8);

    // birth+death year labels
    rows.append("text")
      .attr("x", (d) => x(d._by) - 4).attr("y", 4)
      .attr("text-anchor", "end")
      .style("font-family", "'Cormorant SC', Georgia, serif")
      .style("font-size", "9px").style("fill", "#7a4a1f")
      .text((d) => d._by);
    rows.append("text")
      .attr("x", (d) => x(d._dy) + 4).attr("y", 4)
      .style("font-family", "'Cormorant SC', Georgia, serif")
      .style("font-size", "9px").style("fill", "#7a4a1f")
      .text((d) => d.deathYear ? d.deathYear : "?");

    // Era labels at top
    svg.append("g").selectAll("text.era-lbl")
      .data(eras).enter()
      .append("text")
      .attr("x", (d) => x((d[0] + d[1]) / 2))
      .attr("y", margin.top - 14)
      .attr("text-anchor", "middle")
      .style("font-family", "'Cormorant SC', Georgia, serif")
      .style("font-size", "9px").style("letter-spacing", "0.18em")
      .style("fill", "#7a4a1f").style("text-transform", "uppercase")
      .text((d) => d[2]);
  }

  // ============================================================
  //   VIEW 3 — Migration Map (Leaflet)
  // ============================================================
  function drawMap() {
    const container = document.getElementById("view-map");

    if (!state._leafletMap) {
      container.innerHTML = '<div id="leaflet-host" style="width:100%; height:640px;"></div>';
      const map = L.map("leaflet-host", { worldCopyJump: true }).setView([42.0, -50.0], 3);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 18,
      }).addTo(map);
      state._leafletMap = map;
      state._mapLayers = L.layerGroup().addTo(map);
    }

    const map = state._leafletMap;
    const layers = state._mapLayers;
    layers.clearLayers();

    // Plot every person's birth & death points; draw migration arc (birth → death) when both known
    const focused = state.byId.get(state.focusedId);
    const featuredIds = new Set();
    if (focused) {
      featuredIds.add(focused.id);
      if (focused.father) featuredIds.add(focused.father);
      if (focused.mother) featuredIds.add(focused.mother);
      if (focused.spouse) featuredIds.add(focused.spouse);
      (focused.children || []).forEach((c) => featuredIds.add(c));
    }

    state.people.forEach((p) => {
      const isFeatured = featuredIds.has(p.id);
      const opacity = isFeatured ? 1.0 : 0.45;
      const radius = isFeatured ? 9 : 6;

      if (p.birthGeo) {
        const m = L.circleMarker([p.birthGeo.lat, p.birthGeo.lng], {
          radius, color: branchHex(p.branch), weight: 2, fillColor: "#f4ead5",
          fillOpacity: opacity, opacity,
        }).bindTooltip(
          `<strong>${p.name}</strong><br><em>born</em> ${p.birth || ""}<br>${p.birthGeo.label}`,
          { direction: "top" }
        ).on("click", () => focusOn(p.id));
        layers.addLayer(m);
      }
      if (p.deathGeo && p.birthGeo &&
          (p.deathGeo.lat !== p.birthGeo.lat || p.deathGeo.lng !== p.birthGeo.lng)) {
        // migration arc — only for the focused person & their immediate kin
        if (isFeatured) {
          const arc = L.polyline([
            [p.birthGeo.lat, p.birthGeo.lng],
            [p.deathGeo.lat, p.deathGeo.lng],
          ], {
            color: branchHex(p.branch), weight: 2, opacity: 0.8, dashArray: "5 6",
          });
          layers.addLayer(arc);
        }
        const dm = L.circleMarker([p.deathGeo.lat, p.deathGeo.lng], {
          radius: radius - 1, color: branchHex(p.branch), weight: 2, fillColor: branchHex(p.branch),
          fillOpacity: opacity * 0.6, opacity,
        }).bindTooltip(
          `<strong>${p.name}</strong><br><em>died</em> ${p.death || ""}<br>${p.deathGeo.label}`,
          { direction: "top" }
        ).on("click", () => focusOn(p.id));
        layers.addLayer(dm);
      }
    });

    // Pan/zoom to focused person if they have geo
    if (focused) {
      const target = focused.birthGeo || focused.deathGeo;
      if (target) {
        map.flyTo([target.lat, target.lng], 5, { duration: 0.8 });
      }
    }
  }

  // ----- helpers -----
  function truncate(s, n) {
    if (!s) return "";
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }
})();
