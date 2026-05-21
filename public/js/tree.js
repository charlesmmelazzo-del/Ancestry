// ============================================================
//   Family tree — interactive (Pedigree / Timeline / Map)
//   Shared by all family sites. Reads window.TREE_CONFIG for
//   per-family overrides; falls back to Quesenberry defaults.
// ============================================================

import { select, hierarchy, tree as d3tree, zoom, zoomIdentity } from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

// ---------- family config (injected per page) ----------
const _cfg    = window.TREE_CONFIG || {};
const DATA_URL   = _cfg.dataUrl  || "/tree.json";
const ROOT_IDS   = (_cfg.rootIds && _cfg.rootIds.length)
                     ? _cfg.rootIds
                     : ["lonnie-quesenberry", "ruth-harvey"];
const DESC_ROOTS = new Set(ROOT_IDS);

// ---------- shared state ----------
const state = {
  people: [],
  byId: new Map(),
  view: "pedigree",
  focusedId: null,
  searchActiveIndex: -1,
  pedSvg: null,
  pedZoom: null,
  pedZoomRoot: null,
  pedFitTransform: null,
  pedMaxDepth: 4,
  leafletReady: false,
  leafletMap: null,
  leafletLayers: null,
};

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const MS_FOCUS = REDUCED ? 0 : 750;
const MS_FADE  = REDUCED ? 0 : 700;

// ---------- helpers ----------
const $ = (sel, ctx) => (ctx || document).querySelector(sel);
const $$ = (sel, ctx) => Array.from((ctx || document).querySelectorAll(sel));

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
function truncate(s, n) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
function isMobile() {
  return window.matchMedia("(max-width: 768px)").matches;
}
function paramsFromUrl() {
  const u = new URL(window.location.href);
  return {
    view: u.searchParams.get("view") || "pedigree",
    focus: u.searchParams.get("focus") || null,
  };
}
function setUrlState({ view, focus }) {
  const u = new URL(window.location.href);
  if (view) u.searchParams.set("view", view); else u.searchParams.delete("view");
  if (focus) u.searchParams.set("focus", focus); else u.searchParams.delete("focus");
  window.history.replaceState({}, "", u);
}

// ---------- bootstrap ----------
fetch(DATA_URL)
  .then((r) => r.json())
  .then((data) => {
    state.people = data.people;
    state.people.forEach((p) => state.byId.set(p.id, p));

    const u = paramsFromUrl();
    state.view = ["pedigree", "timeline", "map"].includes(u.view) ? u.view : "pedigree";
    // Default focus: first ROOT_ID that exists in data, then first person overall.
    const defaultFocus = ROOT_IDS.find(id => state.byId.has(id)) || state.people[0]?.id || null;
    state.focusedId = u.focus && state.byId.has(u.focus) ? u.focus : defaultFocus;

    initToolbar();
    initSearch();
    initFindMe();
    initKeyboardShortcuts();
    initResize();

    drawPedigree();
    if (state.view !== "pedigree") switchView(state.view, /*animate*/ false, /*initial*/ true);
    if (state.view === "timeline") drawTimeline();
    if (state.view === "map") activateMap();
    renderSidePanel();
    maybeShowStartHere();
  })
  .catch((e) => {
    $("#view-pedigree").innerHTML =
      "<p style='padding:2rem; color:var(--rust);'>Could not load tree data: " +
      escapeHtml(String(e)) + "</p>";
  });

// ============================================================
//   Toolbar / view switching
// ============================================================
function initToolbar() {
  $$(".view-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = btn.dataset.view;
      switchView(v, /*animate*/ true);
    });
  });

  $(".zoom-in")?.addEventListener("click", () => zoomBy(1.4));
  $(".zoom-out")?.addEventListener("click", () => zoomBy(1 / 1.4));
  $(".zoom-fit")?.addEventListener("click", () => fitPedigreeToViewport());
  $(".gen-inc")?.addEventListener("click", () => changeGenDepth(1));
  $(".gen-dec")?.addEventListener("click", () => changeGenDepth(-1));
}

function switchView(v, animate, initial) {
  if (!["pedigree", "timeline", "map"].includes(v)) return;
  state.view = v;
  setUrlState({ view: v, focus: state.focusedId });

  $$(".view-tab").forEach((b) => {
    const active = b.dataset.view === v;
    b.classList.toggle("active", active);
    b.setAttribute("aria-selected", active ? "true" : "false");
  });

  const views = $$(".tree-stage .view");
  if (animate && !REDUCED && !initial) {
    views.forEach((el) => {
      el.classList.add("fading");
    });
    setTimeout(() => applyView(v, views), MS_FADE / 2);
    setTimeout(() => views.forEach((el) => el.classList.remove("fading")), MS_FADE);
  } else {
    applyView(v, views);
  }
}
function applyView(v, views) {
  views.forEach((el) => {
    const active = el.id === "view-" + v;
    el.classList.toggle("active", active);
    if (active) el.removeAttribute("hidden");
    else el.setAttribute("hidden", "");
  });
  if (v === "timeline") drawTimeline();
  if (v === "map") activateMap();
  if (v === "pedigree" && state.pedSvg && !isMobile()) {
    // Re-fit if dimensions changed (e.g., after a resize during a hidden state).
    requestAnimationFrame(() => fitPedigreeToViewport(/*soft*/ true));
  }
}

// ============================================================
//   Search with keyboard nav
// ============================================================
function initSearch() {
  const input = $("#search");
  const results = $("#search-results");

  function render(matches) {
    results.innerHTML = matches.map((p, i) =>
      `<li role="option" id="sr-${i}" data-id="${p.id}">
         <span class="nm">${escapeHtml(p.name)}</span>
         <span class="ls">${escapeHtml(p.lifespan || "")}</span>
       </li>`
    ).join("");
    results.hidden = matches.length === 0;
    input.setAttribute("aria-expanded", matches.length ? "true" : "false");
    state.searchActiveIndex = matches.length ? 0 : -1;
    paintActive();
  }
  function paintActive() {
    const items = $$("li", results);
    items.forEach((li, i) => li.classList.toggle("active", i === state.searchActiveIndex));
    if (state.searchActiveIndex >= 0 && items[state.searchActiveIndex]) {
      input.setAttribute("aria-activedescendant", items[state.searchActiveIndex].id);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }
  function currentMatches() {
    const q = input.value.trim().toLowerCase();
    if (!q) return [];
    return state.people
      .filter((p) => p.name.toLowerCase().includes(q))
      .slice(0, 8);
  }

  input.addEventListener("input", () => render(currentMatches()));
  input.addEventListener("keydown", (e) => {
    const items = $$("li", results);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!items.length) { render(currentMatches()); return; }
      state.searchActiveIndex = (state.searchActiveIndex + 1) % items.length;
      paintActive();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!items.length) return;
      state.searchActiveIndex = (state.searchActiveIndex - 1 + items.length) % items.length;
      paintActive();
    } else if (e.key === "Enter") {
      const items = $$("li", results);
      const li = items[state.searchActiveIndex] || items[0];
      if (li) {
        e.preventDefault();
        focusOn(li.dataset.id);
        input.value = "";
        results.hidden = true;
        input.setAttribute("aria-expanded", "false");
        input.blur();
      }
    } else if (e.key === "Escape") {
      input.value = "";
      results.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.blur();
    }
  });

  results.addEventListener("mousedown", (e) => {
    const li = e.target.closest("li[data-id]");
    if (!li) return;
    e.preventDefault();
    focusOn(li.dataset.id);
    input.value = "";
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
  });
  input.addEventListener("blur", () => {
    setTimeout(() => {
      results.hidden = true;
      input.setAttribute("aria-expanded", "false");
    }, 150);
  });
}

// ============================================================
//   "Find me on the tree" dialog
// ============================================================
function initFindMe() {
  const btn = $("#find-me");
  const dlg = $("#find-me-dialog");
  if (!btn || !dlg) return;

  btn.addEventListener("click", () => {
    if (typeof dlg.showModal === "function") dlg.showModal();
    else dlg.setAttribute("open", "");
  });
  $(".find-me-cancel", dlg)?.addEventListener("click", () => dlg.close("cancel"));
  $(".find-me-form", dlg)?.addEventListener("submit", (e) => {
    e.preventDefault();
    const sel = $("#find-me-select");
    const id = sel?.value;
    dlg.close("confirm");
    if (id && state.byId.has(id)) {
      // Switch to pedigree view if not already
      if (state.view !== "pedigree") switchView("pedigree", true);
      focusOn(id);
      highlightPathToRoot(id);
    }
  });
}

function highlightPathToRoot(fromId) {
  const path = pathToDescendantRoot(fromId);
  if (!path) return;
  const ids = new Set([fromId, ...path]);
  // Add a temporary CSS class to nodes whose data-id is in the set
  setTimeout(() => {
    $$(".ped-node").forEach((g) => {
      g.classList.toggle("path-highlight", ids.has(g.dataset.id));
    });
    $$(".ped-link").forEach((p) => {
      const a = p.dataset.from, b = p.dataset.to;
      p.classList.toggle("path-highlight", ids.has(a) && ids.has(b));
    });
  }, 50);
  setTimeout(() => {
    $$(".ped-node.path-highlight").forEach((g) => g.classList.remove("path-highlight"));
    $$(".ped-link.path-highlight").forEach((p) => p.classList.remove("path-highlight"));
  }, 4500);
}

// ============================================================
//   Keyboard shortcuts (Esc closes panel, "/" focuses search)
// ============================================================
function initKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const dlg = $("#find-me-dialog");
      if (dlg?.open) return;  // dialog handles its own Esc
      if (state.focusedId) {
        state.focusedId = null;
        setUrlState({ view: state.view, focus: null });
        renderSidePanel();
        repaintFocus();
        $(".side-panel")?.classList.remove("open");
      }
    } else if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      $("#search")?.focus();
    }
  });
}

// ============================================================
//   Resize
// ============================================================
function initResize() {
  let raf = null;
  let prevMobile = isMobile();
  window.addEventListener("resize", () => {
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const m = isMobile();
      if (m !== prevMobile) {
        prevMobile = m;
        drawPedigree();
        if (state.view === "timeline") drawTimeline();
      } else if (state.view === "pedigree" && !m) {
        fitPedigreeToViewport(/*soft*/ true);
      }
      if (state.view === "map" && state.leafletMap) {
        state.leafletMap.invalidateSize();
      }
    });
  });
}

// ============================================================
//   Focus + side panel
// ============================================================
function focusOn(id) {
  if (!state.byId.has(id)) return;
  state.focusedId = id;
  setUrlState({ view: state.view, focus: id });
  renderSidePanel();
  repaintFocus();
  if (state.view === "pedigree" && state.pedSvg && !isMobile()) {
    panToNode(id);
  } else if (state.view === "timeline") {
    drawTimeline();
  } else if (state.view === "map" && state.leafletMap) {
    drawMapMarkers();
  }
  // Open mobile bottom sheet
  if (isMobile()) $(".side-panel")?.classList.add("open");
  hideStartHere();
}

function repaintFocus() {
  $$(".ped-node").forEach((g) => {
    g.classList.toggle("focused", g.dataset.id === state.focusedId);
  });
  $$(".tl-row").forEach((g) => {
    g.classList.toggle("focused", g.dataset.id === state.focusedId);
  });
}

function pathToDescendantRoot(fromId) {
  if (DESC_ROOTS.has(fromId)) return [];
  const visited = new Set([fromId]);
  const queue = [[fromId]];
  while (queue.length) {
    const path = queue.shift();
    const last = path[path.length - 1];
    const p = state.byId.get(last);
    if (!p) continue;
    for (const cid of p.children || []) {
      if (visited.has(cid)) continue;
      visited.add(cid);
      const next = path.concat(cid);
      if (DESC_ROOTS.has(cid)) return next.slice(1);
      queue.push(next);
    }
  }
  return null;
}

function nameById(id) {
  return state.byId.get(id)?.name || humanizeId(id);
}
function humanizeId(id) {
  return String(id).split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");
}
function shortName(id) {
  const n = nameById(id);
  return n.split(" ")[0];
}

function postmark(verified) {
  const map = {
    documented: ["#3a5a3e", "Documented"],
    partial:    ["#8a6d28", "Partial"],
    tradition:  ["#7a4a1f", "Tradition"],
  };
  const [color, label] = map[verified] || ["#4a3520", "Undocumented"];
  return `<span class="postmark" data-status="${verified || "unknown"}">
    <svg viewBox="0 0 56 56" aria-hidden="true">
      <circle cx="28" cy="28" r="24" fill="none" stroke="${color}" stroke-width="1.4"></circle>
      <circle cx="28" cy="28" r="20" fill="none" stroke="${color}" stroke-width="0.8" stroke-dasharray="2 2"></circle>
    </svg>
    <span class="postmark-label" style="color:${color}">${label}</span>
  </span>`;
}

function renderSidePanel() {
  const panel = $("#side-panel");
  const p = state.byId.get(state.focusedId);
  if (!p) {
    panel.innerHTML = "<p class='muted'>Click any name to focus on a person.</p>";
    return;
  }

  const facts = [];
  if (p.birth) facts.push(["Born", `${escapeHtml(p.birth)}${p.birthPlace ? ", " + escapeHtml(p.birthPlace) : ""}`]);
  if (p.death) facts.push(["Died", `${escapeHtml(p.death)}${p.deathPlace ? ", " + escapeHtml(p.deathPlace) : ""}`]);
  if (p.burial) facts.push(["Buried", escapeHtml(p.burial)]);
  if (p.military) facts.push(["Military", escapeHtml(p.military)]);

  const branchHex = p.monogramColor || "#4a3520";
  const branchLabel = (p.branch || "").toUpperCase();

  // Where they sit — 4 lines
  const parents = [p.father, p.mother].filter(Boolean).map(linkName).join(" &nbsp; ");
  const spouseLine = p.spouse ? linkName(p.spouse) : "";
  const childrenLine = (p.children || []).map(linkName).join(" &nbsp; ");

  // Path to Lonnie & Ruth
  const path = pathToDescendantRoot(p.id);
  let pathHtml = "";
  if (path && path.length) {
    const segments = [shortName(p.id), ...path.map(shortName)];
    pathHtml = `<p class="panel-path">${segments.map(escapeHtml).join(" → ")}</p>`;
  }

  panel.innerHTML = `
    <div class="panel-head" style="border-left: 4px solid ${branchHex};">
      <p class="panel-eyebrow">${escapeHtml(branchLabel)} LINE · GEN ${p.generation ?? "?"}</p>
      <h3 class="panel-name" id="side-panel-name">${escapeHtml(p.name)}</h3>
      <p class="panel-lifespan">${escapeHtml(p.lifespan || "")}</p>
      ${postmark(p.verified)}
    </div>
    ${p.epitaph ? `<p class="panel-epitaph"><em>${escapeHtml(p.epitaph)}</em></p>` : ""}

    <div class="panel-where-they-sit">
      <p class="panel-section-label">Where they sit</p>
      ${parents ? `<p class="wts-row wts-parents"><span class="wts-tag">Parents</span> ${parents}</p>` : ""}
      <p class="wts-row wts-self"><span class="wts-tag">This is</span> <em>${escapeHtml(p.name)}</em></p>
      ${spouseLine ? `<p class="wts-row wts-spouse"><span class="wts-tag">Spouse</span> ${spouseLine}</p>` : ""}
      ${childrenLine ? `<p class="wts-row wts-children"><span class="wts-tag">Children</span> ${childrenLine}</p>` : ""}
    </div>

    ${pathHtml ? `<div class="panel-path-wrap">
      <p class="panel-section-label">Path to Lonnie & Ruth</p>
      ${pathHtml}
    </div>` : ""}

    <dl class="panel-facts">
      ${facts.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}
    </dl>

    <div class="panel-actions">
      <a class="panel-link" href="/people/${p.id}.html">Read full profile →</a>
      ${isMobile() ? '<button type="button" class="panel-close-mobile" aria-label="Close panel">Close</button>' : ""}
    </div>
  `;

  // Wire mobile close
  $(".panel-close-mobile", panel)?.addEventListener("click", () => {
    panel.classList.remove("open");
  });
}

function linkName(id) {
  const p = state.byId.get(id);
  if (!p) {
    return `<span class="person-stub" title="No record yet">${escapeHtml(humanizeId(id))}</span>`;
  }
  return `<a href="#" data-focus="${id}">${escapeHtml(p.name)}</a>`;
}

// Delegate clicks on panel-internal data-focus links
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-focus]");
  if (a) {
    e.preventDefault();
    focusOn(a.dataset.focus);
  }
});

// ============================================================
//   "Start here" callout
// ============================================================
function maybeShowStartHere() {
  const u = paramsFromUrl();
  if (u.focus) return;
  if (sessionStorage.getItem("starthere_dismissed") === "1") return;
  const el = $("#start-here-callout");
  if (!el) return;
  el.hidden = false;
  el.classList.add("visible");
}
function hideStartHere() {
  const el = $("#start-here-callout");
  if (!el || el.hidden) return;
  el.classList.remove("visible");
  setTimeout(() => { el.hidden = true; }, REDUCED ? 0 : 320);
  sessionStorage.setItem("starthere_dismissed", "1");
}

// ============================================================
//   Pedigree view
// ============================================================
function drawPedigree() {
  const container = $("#view-pedigree");
  container.innerHTML = "";
  state.pedSvg = null;
  state.pedZoom = null;
  state.pedZoomRoot = null;

  if (isMobile()) {
    drawPedigreeMobile(container);
    return;
  }
  drawPedigreeDesktop(container);
}

function drawPedigreeDesktop(container) {
  const firstRootId = ROOT_IDS.find(id => state.byId.has(id));
  if (!firstRootId && state.people.length === 0) {
    container.innerHTML = `<p class="tree-empty">No ancestors have been added to this tree yet. <a href="/submit.html">Contribute records</a> to get started.</p>`;
    return;
  }
  if (!firstRootId) return;

  // Build hierarchy by walking parents upward from root IDs.
  function build(personId, depth, seen = new Set()) {
    if (seen.has(personId)) return null;
    const p = state.byId.get(personId);
    if (!p || depth > state.pedMaxDepth - 1) return null;
    const next = new Set(seen).add(personId);
    const node = { id: p.id, person: p, children: [] };
    if (p.father && state.byId.has(p.father)) {
      const f = build(p.father, depth + 1, next);
      if (f) node.children.push(f);
    }
    if (p.mother && state.byId.has(p.mother)) {
      const m = build(p.mother, depth + 1, next);
      if (m) node.children.push(m);
    }
    return node;
  }

  const rootTrees = ROOT_IDS.map(id => build(id, 0)).filter(Boolean);
  // Couple label from first two roots' names, or a generic label.
  const coupleLabel = rootTrees.length >= 2
    ? `${rootTrees[0].person.name.split(" ")[0]} & ${rootTrees[1].person.name.split(" ")[0]}`
    : (rootTrees[0]?.person.name || "Family");
  const data = {
    id: "__couple__",
    person: { name: coupleLabel, branch: "" },
    children: rootTrees,
  };

  const w = container.clientWidth || 900;
  const h = 720;

  const svg = select(container).append("svg")
    .attr("class", "ped-svg")
    .attr("viewBox", `0 0 ${w} ${h}`)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("width", "100%")
    .style("height", h + "px")
    .attr("role", "application")
    .attr("aria-label", "Family pedigree, pan and zoom enabled");

  const zoomRoot = svg.append("g").attr("class", "zoom-root");
  state.pedSvg = svg;
  state.pedZoomRoot = zoomRoot;

  // Fixed per-node spacing so nodes never overlap regardless of tree depth or breadth.
  // nodeSize([dx, dy]): each node is guaranteed dx px horizontally, dy px vertically.
  const root = hierarchy(data);
  d3tree().nodeSize([110, 130])(root);

  // links
  const realLinks = root.links().filter((l) => l.source.data.id !== "__couple__");
  zoomRoot.append("g").attr("class", "links")
    .selectAll("path")
    .data(realLinks)
    .enter()
    .append("path")
    .attr("class", "ped-link")
    .attr("data-from", (d) => d.target.data.id)
    .attr("data-to",   (d) => d.source.data.id)
    .attr("fill", "none")
    .attr("d", (d) => {
      const s = d.source, t = d.target;
      const my = (s.y + t.y) / 2;
      return `M${s.x},${s.y} C${s.x},${my} ${t.x},${my} ${t.x},${t.y}`;
    });

  // Spouse line between Lonnie & Ruth
  if (root.children?.length === 2) {
    const a = root.children[0], b = root.children[1];
    zoomRoot.append("line")
      .attr("class", "spouse-line")
      .attr("x1", a.x).attr("y1", a.y)
      .attr("x2", b.x).attr("y2", b.y);
  }

  // nodes (skip synthetic couple root)
  const nodes = root.descendants().filter((d) => d.data.id !== "__couple__");
  const node = zoomRoot.append("g").attr("class", "nodes")
    .selectAll("g.ped-node")
    .data(nodes)
    .enter()
    .append("g")
    .attr("class", (d) => `ped-node branch-${d.data.person.branch || "unknown"}`)
    .attr("data-id", (d) => d.data.id)
    .attr("transform", (d) => `translate(${d.x},${d.y})`)
    .attr("tabindex", "0")
    .attr("role", "button")
    .attr("aria-label", (d) => {
      const p = d.data.person;
      return `${p.name}${p.lifespan ? ", " + p.lifespan : ""}. Press Enter to focus.`;
    })
    .classed("focused", (d) => d.data.id === state.focusedId)
    .on("click", (e, d) => focusOn(d.data.id))
    .on("keydown", (e, d) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        focusOn(d.data.id);
      }
    })
    .on("mouseenter", function (e, d) { showHoverCard(e, d.data.person); })
    .on("mousemove", function (e) { moveHoverCard(e); })
    .on("mouseleave", function () { hideHoverCard(); });

  // hit target — 104px fits within the 110px nodeSize gap so adjacent targets never overlap
  node.append("rect")
    .attr("class", "ped-hit")
    .attr("x", -52).attr("y", -52)
    .attr("width", 104).attr("height", 104)
    .attr("fill", "transparent");

  // outer ring (focus highlight)
  node.append("circle")
    .attr("class", "ped-focus-ring")
    .attr("r", 30)
    .attr("fill", "none");

  // monogram disk
  node.append("circle")
    .attr("class", "ped-disk")
    .attr("r", 24)
    .attr("fill", "var(--paper)")
    .attr("stroke", (d) => d.data.person.monogramColor || "#4a3520")
    .attr("stroke-width", 2);

  // initials
  node.append("text")
    .attr("class", "ped-monogram")
    .attr("text-anchor", "middle")
    .attr("dominant-baseline", "central")
    .attr("y", 0)
    .text((d) => d.data.person.initials || "·");

  // name below
  node.append("text")
    .attr("class", "ped-name")
    .attr("text-anchor", "middle")
    .attr("y", 44)
    .text((d) => truncate(d.data.person.name, 22));

  // dates below name
  node.append("text")
    .attr("class", "ped-dates")
    .attr("text-anchor", "middle")
    .attr("y", 60)
    .text((d) => d.data.person.lifespan || "");

  // d3-zoom behavior — owns all transforms on zoomRoot (no fixed margin offset)
  state.pedZoom = zoom()
    .scaleExtent([0.08, 4])
    .on("zoom", (e) => {
      zoomRoot.attr("transform",
        `translate(${e.transform.x},${e.transform.y}) scale(${e.transform.k})`
      );
    });

  svg.call(state.pedZoom);

  // Disable double-click zoom (we'll use it for focus instead).
  svg.on("dblclick.zoom", null);

  // "Fit" button always shows all nodes.
  state.pedFitTransform = computeFitTransform(nodes, w, h, { top: 40, right: 40, bottom: 40, left: 40 });

  // Initial view: scale so the depth-1 roots (Lonnie & Ruth) are visible near the
  // top at a comfortable size, rather than zooming all the way out to fit every leaf.
  const d1 = (root.children || []).filter(c => c.data.id !== "__couple__");
  if (d1.length >= 2) {
    const d1xMin = Math.min(...d1.map(n => n.x));
    const d1xMax = Math.max(...d1.map(n => n.x));
    const d1y = d1[0].y;
    const initK = Math.min(w * 0.90 / (d1xMax - d1xMin + 110), 1.0);
    const initTx = w / 2 - ((d1xMin + d1xMax) / 2) * initK;
    const initTy = h * 0.22 - d1y * initK;
    applyZoomTransform(zoomIdentity.translate(initTx, initTy).scale(initK), false);
  } else {
    applyZoomTransform(state.pedFitTransform, /*animate*/ false);
  }

  // Pan to focused person if it's not one of the root IDs — those are already
  // prominently visible in the initial view above.
  if (state.focusedId && !ROOT_IDS.includes(state.focusedId)) {
    requestAnimationFrame(() => panToNode(state.focusedId));
  }
}

function computeFitTransform(nodes, w, h, margin) {
  if (!nodes?.length) return zoomIdentity;
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs) - 60;
  const maxX = Math.max(...xs) + 60;
  const minY = Math.min(...ys) - 70;
  const maxY = Math.max(...ys) + 70;
  const bw = maxX - minX;
  const bh = maxY - minY;
  const availW = w - margin.left - margin.right;
  const availH = h - margin.top - margin.bottom;
  const k = Math.min(availW / bw, availH / bh, 1.2) * 0.95;
  // We want the centroid of nodes to map to the centroid of the available area.
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const tx = (availW / 2) - (cx * k);
  const ty = (availH / 2) - (cy * k);
  return zoomIdentity.translate(tx, ty).scale(k);
}

function applyZoomTransform(t, animate = true) {
  if (!state.pedSvg || !state.pedZoom) return;
  const sel = animate
    ? state.pedSvg.transition().duration(MS_FOCUS)
    : state.pedSvg;
  sel.call(state.pedZoom.transform, t);
}

function fitPedigreeToViewport(soft) {
  if (!state.pedFitTransform) return;
  applyZoomTransform(state.pedFitTransform, !soft);
}
function changeGenDepth(delta) {
  const next = Math.max(2, Math.min(9, state.pedMaxDepth + delta));
  if (next === state.pedMaxDepth) return;
  state.pedMaxDepth = next;
  const label = $(".gen-label");
  if (label) label.textContent = next;
  if (state.view === "pedigree") drawPedigree();
}
function zoomBy(factor) {
  if (!state.pedSvg || !state.pedZoom) return;
  state.pedSvg.transition().duration(REDUCED ? 0 : 220).call(state.pedZoom.scaleBy, factor);
}

function panToNode(id) {
  const g = $(`.ped-node[data-id="${cssEscape(id)}"]`);
  if (!g || !state.pedSvg || !state.pedZoom) return;
  // Get the node's untransformed (x,y) by reading transform attr.
  const m = (g.getAttribute("transform") || "").match(/translate\(([-\d.]+),\s*([-\d.]+)\)/);
  if (!m) return;
  const nx = parseFloat(m[1]);
  const ny = parseFloat(m[2]);
  const svgEl = state.pedSvg.node();
  const vb = svgEl.viewBox.baseVal;
  const w = vb.width || svgEl.clientWidth || 900;
  const h = vb.height || svgEl.clientHeight || 720;
  const cur = currentZoomTransform();
  const k = cur.k;
  const tx = w / 2 - nx * k;
  const ty = h / 2 - ny * k;
  applyZoomTransform(zoomIdentity.translate(tx, ty).scale(k), true);
}
function currentZoomTransform() {
  // d3-zoom stores transform on the svg node via its wrapper
  if (!state.pedSvg) return zoomIdentity;
  // Re-derive from the zoom-root's transform attr is hard, so we keep a hook on svg:
  return state.pedSvg.node().__zoom || zoomIdentity;
}
function cssEscape(s) {
  if (window.CSS?.escape) return CSS.escape(s);
  return String(s).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

// ----- pedigree mobile (indented list) -----
function drawPedigreeMobile(container) {
  const firstRootId = ROOT_IDS.find(id => state.byId.has(id));
  if (!firstRootId && state.people.length === 0) {
    container.innerHTML = `<p class="tree-empty" style="padding:1.5rem">No ancestors added yet.</p>`;
    return;
  }
  if (!firstRootId) return;
  const seen = new Set();
  const ol = document.createElement("ol");
  ol.className = "ped-list";
  ol.setAttribute("aria-label", "Family pedigree as nested list");

  function appendNode(id, depth, into) {
    if (seen.has(id) || depth > state.pedMaxDepth - 1) return;
    seen.add(id);
    const p = state.byId.get(id);
    if (!p) return;
    const li = document.createElement("li");
    li.className = `ped-list-item branch-${p.branch || "unknown"}`;
    li.dataset.id = id;
    li.tabIndex = 0;
    li.setAttribute("role", "button");
    li.setAttribute("aria-label", `${p.name}${p.lifespan ? ", " + p.lifespan : ""}. Tap to focus.`);
    li.style.setProperty("--depth", String(depth));
    li.innerHTML = `
      <span class="pl-disk" style="border-color:${p.monogramColor || "#4a3520"}">${escapeHtml(p.initials || "·")}</span>
      <span class="pl-text">
        <span class="pl-name">${escapeHtml(p.name)}</span>
        <span class="pl-dates">${escapeHtml(p.lifespan || "")}</span>
      </span>`;
    li.addEventListener("click", () => focusOn(id));
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focusOn(id); }
    });
    into.appendChild(li);
    const sublist = document.createElement("ol");
    sublist.className = "ped-list ped-list-children";
    if (p.father) appendNode(p.father, depth + 1, sublist);
    if (p.mother) appendNode(p.mother, depth + 1, sublist);
    if (sublist.children.length) into.appendChild(sublist);
  }

  // Root: all configured root IDs that exist in data
  ROOT_IDS.forEach(id => { if (state.byId.has(id)) appendNode(id, 0, ol); });
  container.appendChild(ol);
  // Reflect focus
  $$(".ped-list-item").forEach((li) => {
    li.classList.toggle("focused", li.dataset.id === state.focusedId);
  });
}

// ============================================================
//   Hover card
// ============================================================
let hoverEl = null;
function ensureHoverCard() {
  if (hoverEl) return hoverEl;
  hoverEl = document.createElement("div");
  hoverEl.className = "hover-card";
  hoverEl.hidden = true;
  document.body.appendChild(hoverEl);
  return hoverEl;
}
function showHoverCard(e, p) {
  if (isMobile()) return;
  const el = ensureHoverCard();
  el.innerHTML = `
    <span class="hc-disk" style="border-color:${p.monogramColor || "#4a3520"}">${escapeHtml(p.initials || "·")}</span>
    <span class="hc-text">
      <span class="hc-name">${escapeHtml(p.name)}</span>
      <span class="hc-dates">${escapeHtml(p.lifespan || "")}</span>
      ${p.birthPlace ? `<span class="hc-place">${escapeHtml(p.birthPlace)}</span>` : ""}
    </span>`;
  el.hidden = false;
  moveHoverCard(e);
}
function moveHoverCard(e) {
  if (!hoverEl || hoverEl.hidden) return;
  const x = e.clientX + 14;
  const y = e.clientY + 14;
  hoverEl.style.left = x + "px";
  hoverEl.style.top = y + "px";
}
function hideHoverCard() {
  if (hoverEl) hoverEl.hidden = true;
}

// ============================================================
//   Timeline view (1600–2030, hard-coded; war eras shaded)
// ============================================================
function drawTimeline() {
  const container = $("#view-timeline");
  container.innerHTML = "";

  const people = state.people
    .filter((p) => p.birthYear)
    .map((p) => ({
      ...p,
      _by: p.birthYear,
      _dy: p.deathYear || Math.min(2030, p.birthYear + 75),
    }))
    .sort((a, b) => a._by - b._by);

  if (!people.length) return;

  const minYear = 1600;
  const maxYear = 2030;
  const w = container.clientWidth || 900;
  const rowH = 28;
  const h = people.length * rowH + 90;
  const margin = { top: 50, right: 30, bottom: 40, left: 220 };

  const svg = select(container).append("svg")
    .attr("class", "tl-svg")
    .attr("viewBox", `0 0 ${w} ${h}`)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("width", "100%")
    .style("height", h + "px")
    .attr("role", "img")
    .attr("aria-label", "Lifespans of family members from 1600 to 2030");

  // diag pattern for "estimate" markers
  const defs = svg.append("defs");
  const pat = defs.append("pattern")
    .attr("id", "diag")
    .attr("patternUnits", "userSpaceOnUse")
    .attr("width", 6).attr("height", 6)
    .attr("patternTransform", "rotate(45)");
  pat.append("rect").attr("width", 6).attr("height", 6).attr("fill", "var(--paper-2)");
  pat.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6)
    .attr("stroke", "#7a4a1f").attr("stroke-width", 2);

  const x = (year) => margin.left +
    ((year - minYear) / (maxYear - minYear)) * (w - margin.left - margin.right);

  // War / depression bands
  const bands = [
    [1775, 1783, "Revolution"],
    [1861, 1865, "Civil War"],
    [1914, 1918, "WWI"],
    [1929, 1939, "Depression"],
    [1939, 1945, "WWII"],
  ];
  svg.append("g").selectAll("rect.tl-band")
    .data(bands).enter()
    .append("rect")
    .attr("class", "tl-band")
    .attr("x", (d) => x(d[0]))
    .attr("y", margin.top)
    .attr("width", (d) => Math.max(0, x(d[1]) - x(d[0])))
    .attr("height", h - margin.top - margin.bottom);

  svg.append("g").selectAll("text.tl-band-label")
    .data(bands).enter()
    .append("text")
    .attr("class", "tl-band-label")
    .attr("x", (d) => (x(d[0]) + x(d[1])) / 2)
    .attr("y", margin.top - 18)
    .attr("text-anchor", "middle")
    .text((d) => d[2]);

  // Decade ticks
  const ticks = [];
  for (let yr = 1600; yr <= 2030; yr += 50) ticks.push(yr);
  const axis = svg.append("g").attr("class", "tl-axis");
  axis.append("line")
    .attr("x1", margin.left).attr("x2", w - margin.right)
    .attr("y1", margin.top - 6).attr("y2", margin.top - 6);
  axis.selectAll("g.tick")
    .data(ticks).enter()
    .append("g")
    .attr("class", "tick")
    .attr("transform", (d) => `translate(${x(d)}, ${margin.top - 6})`)
    .each(function (d) {
      const t = select(this);
      t.append("line").attr("y2", 4);
      t.append("text").attr("y", -6).attr("text-anchor", "middle").text(String(d));
    });

  // Rows (clickable)
  const rows = svg.append("g").selectAll("g.tl-row")
    .data(people).enter()
    .append("g")
    .attr("class", "tl-row")
    .attr("data-id", (d) => d.id)
    .attr("transform", (_, i) => `translate(0,${margin.top + i * rowH + 16})`)
    .attr("tabindex", "0")
    .attr("role", "button")
    .attr("aria-label", (d) => `${d.name}, born ${d._by}${d.deathYear ? ", died " + d.deathYear : ""}`)
    .classed("focused", (d) => d.id === state.focusedId)
    .on("click", (e, d) => focusOn(d.id))
    .on("keydown", (e, d) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focusOn(d.id); }
    });

  // name labels
  rows.append("text")
    .attr("class", "tl-name")
    .attr("x", margin.left - 10).attr("y", 4)
    .attr("text-anchor", "end")
    .text((d) => truncate(d.name, 28));

  // life bars
  rows.append("rect")
    .attr("class", "tl-bar")
    .attr("x", (d) => x(d._by))
    .attr("y", -8)
    .attr("width", (d) => Math.max(2, x(d._dy) - x(d._by)))
    .attr("height", 16)
    .attr("fill", (d) => d.monogramColor || "#4a3520");

  // estimate end markers
  rows.filter((d) => !d.deathYear)
    .append("rect")
    .attr("class", "tl-estimate")
    .attr("x", (d) => x(d._dy) - 10)
    .attr("y", -8).attr("width", 10).attr("height", 16)
    .attr("fill", "url(#diag)").attr("opacity", 0.85);

  // year labels
  rows.append("text")
    .attr("class", "tl-year tl-year-start")
    .attr("x", (d) => x(d._by) - 4).attr("y", 4)
    .attr("text-anchor", "end")
    .text((d) => d._by);
  rows.append("text")
    .attr("class", "tl-year tl-year-end")
    .attr("x", (d) => x(d._dy) + 4).attr("y", 4)
    .text((d) => d.deathYear ? d.deathYear : "?");
}

// ============================================================
//   Map view (lazy-loaded Leaflet)
// ============================================================
function activateMap() {
  if (state.leafletReady) {
    drawMapMarkers();
    setTimeout(() => {
      state.leafletMap?.invalidateSize();
      const focused = state.byId.get(state.focusedId);
      if (focused) {
        const target = focused.birthGeo || focused.deathGeo;
        if (target) state.leafletMap.flyTo([target.lat, target.lng], 5, { duration: REDUCED ? 0 : 0.8 });
      }
    }, 50);
    return;
  }
  ensureLeafletLoaded().then(() => {
    initMap();
    drawMapMarkers();
  }).catch((e) => {
    $("#view-map").innerHTML =
      "<p style='padding:2rem; color:var(--rust);'>Could not load map: " +
      escapeHtml(String(e)) + "</p>";
  });
}

function ensureLeafletLoaded() {
  if (window.L) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("leaflet.js failed to load"));
    document.head.appendChild(s);
  });
}

function initMap() {
  const container = $("#view-map");
  container.innerHTML = '<div id="leaflet-host" class="leaflet-host"></div>';
  const map = L.map("leaflet-host", { worldCopyJump: true, keyboard: true })
    .setView([42.0, -50.0], 3);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; ' +
      '<a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 18,
  }).addTo(map);
  state.leafletMap = map;
  state.leafletLayers = L.layerGroup().addTo(map);
  state.leafletReady = true;
}

function drawMapMarkers() {
  if (!state.leafletReady) return;
  const map = state.leafletMap;
  const layers = state.leafletLayers;
  layers.clearLayers();

  const focused = state.byId.get(state.focusedId);
  const featuredIds = new Set();
  if (focused) {
    featuredIds.add(focused.id);
    if (focused.father) featuredIds.add(focused.father);
    if (focused.mother) featuredIds.add(focused.mother);
    if (focused.spouse) featuredIds.add(focused.spouse);
    (focused.children || []).forEach((c) => featuredIds.add(c));
  }

  // Faint arcs for everyone, full arcs for featured set.
  state.people.forEach((p) => {
    if (!p.birthGeo) return;
    const isFeatured = featuredIds.has(p.id);
    const opacity = isFeatured ? 1.0 : 0.45;
    const radius = isFeatured ? 9 : 6;
    const color = p.monogramColor || "#4a3520";

    const m = L.circleMarker([p.birthGeo.lat, p.birthGeo.lng], {
      radius, color, weight: 2, fillColor: "#f4ead5",
      fillOpacity: opacity, opacity,
      keyboard: true,
    }).bindTooltip(
      `<strong>${escapeHtml(p.name)}</strong><br><em>born</em> ${escapeHtml(p.birth || "")}<br>${escapeHtml(p.birthGeo.label || "")}`,
      { direction: "top" }
    ).on("click", () => focusOn(p.id));
    layers.addLayer(m);

    if (p.deathGeo &&
        (p.deathGeo.lat !== p.birthGeo.lat || p.deathGeo.lng !== p.birthGeo.lng)) {
      const arc = L.polyline([
        [p.birthGeo.lat, p.birthGeo.lng],
        [p.deathGeo.lat, p.deathGeo.lng],
      ], {
        color, weight: isFeatured ? 2 : 1.2,
        opacity: isFeatured ? 0.85 : 0.30,
        dashArray: "5 6",
      });
      layers.addLayer(arc);

      const dm = L.circleMarker([p.deathGeo.lat, p.deathGeo.lng], {
        radius: radius - 1, color, weight: 2, fillColor: color,
        fillOpacity: opacity * 0.55, opacity,
        keyboard: true,
      }).bindTooltip(
        `<strong>${escapeHtml(p.name)}</strong><br><em>died</em> ${escapeHtml(p.death || "")}<br>${escapeHtml(p.deathGeo.label || "")}`,
        { direction: "top" }
      ).on("click", () => focusOn(p.id));
      layers.addLayer(dm);
    }
  });

  // flyTo is deferred to activateMap's setTimeout so it fires after
  // invalidateSize — calling flyTo while the container is zero-sized throws
  // "Invalid LatLng object: (NaN, NaN)" from Leaflet's unproject.
}
