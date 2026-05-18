#!/usr/bin/env python3
"""
Build script for the Quesenberry & Harvey Family History static site.

Reads data/people.json and renders HTML pages into public/.
Run:  python3 build.py
"""

import html
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "people.json"
PUBLIC = ROOT / "public"
PEOPLE_DIR = PUBLIC / "people"
BRANCH_DIR = PUBLIC / "branches"

try:
    with open(DATA) as f:
        DATABASE = json.load(f)
except FileNotFoundError:
    raise SystemExit(f"build.py: cannot find {DATA}. Run from the project root.")
except json.JSONDecodeError as e:
    raise SystemExit(f"build.py: {DATA} is not valid JSON ({e}).")

for required in ("people", "site"):
    if required not in DATABASE:
        raise SystemExit(f"build.py: {DATA} is missing required top-level key '{required}'.")

PEOPLE = DATABASE["people"]
SITE = DATABASE["site"]
for required in ("title", "intro", "tagline"):
    if required not in SITE:
        raise SystemExit(f"build.py: {DATA} 'site' object is missing '{required}'.")

# ---- optional module data files (Phase 3) ----------------------------------
def _load_optional(name, key, default):
    path = ROOT / "data" / name
    if not path.exists():
        return default
    try:
        with open(path) as fh:
            d = json.load(fh)
        return d.get(key, default)
    except Exception as e:
        print(f"  ! could not load {name}: {e}")
        return default

PHOTOS    = _load_optional("photos.json",    "photos",    [])
STORIES   = _load_optional("stories.json",   "stories",   [])
HEIRLOOMS = _load_optional("heirlooms.json", "heirlooms", [])
PLACES    = _load_optional("places.json",    "places",    [])


# ---- helpers ----------------------------------------------------------------

def md_to_html(text: str) -> str:
    """Tiny markdown-ish: *italic* and **bold** inline only."""
    text = html.escape(text or "")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def md_to_paragraphs(text: str) -> str:
    """Split on \\n\\n, run inline md, wrap each in <p>."""
    if not text:
        return ""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n".join(f"<p>{md_to_html(p)}</p>" for p in paras)


def person_link(person_id):
    if person_id in PEOPLE:
        p = PEOPLE[person_id]
        return f'<a href="/people/{person_id}.html">{p["name"]}</a>'
    name = " ".join(w.capitalize() for w in person_id.replace("_", "-").split("-"))
    return f'<span class="person-stub" title="No record yet">{name}</span>'


def safe(d, key, default=""):
    v = d.get(key, default)
    return v if v is not None else default


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


# ---- shared chrome ----------------------------------------------------------

def head(title, page_path=""):
    """Compute relative path back to root from the page URL."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — {SITE['title']}</title>
<meta name="description" content="{SITE['intro']}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&family=Cormorant+SC:wght@400;500&family=Special+Elite&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/style.css">
</head>
<body>
"""


def header(active=""):
    def cls(name):
        return ' class="active"' if name == active else ""
    branch_active = "active" if active in ("quesenberry", "harvey", "carmichael") else ""
    archive_active = "active" if active in ("archive", "stories", "places", "heirlooms") else ""
    more_active = "active" if active in ("military", "sources", "open-questions", "submit") else ""
    return f"""<header class="site-header">
  <div class="shell">
    <p class="site-title"><a href="/">{SITE['title']}</a></p>
    <nav class="site-nav" aria-label="Main">
      <a href="/tree.html"{cls('tree')}>Tree</a>
      <details>
        <summary class="{branch_active}">Branches</summary>
        <div class="more-menu">
          <a href="/branches/quesenberry.html"{cls('quesenberry')}>Quesenberry</a>
          <a href="/branches/harvey.html"{cls('harvey')}>Harvey</a>
          <a href="/branches/carmichael.html"{cls('carmichael')}>Carmichael</a>
        </div>
      </details>
      <a href="/timeline.html"{cls('timeline')}>Timeline</a>
      <details>
        <summary class="{archive_active}">Archive</summary>
        <div class="more-menu">
          <a href="/photographs.html"{cls('archive')}>Photographs</a>
          <a href="/stories.html"{cls('stories')}>Stories &amp; Oral Histories</a>
          <a href="/places.html"{cls('places')}>Places &amp; Migration</a>
          <a href="/heirlooms.html"{cls('heirlooms')}>Heirlooms &amp; Recipes</a>
        </div>
      </details>
      <a href="/submit.html"{cls('submit')}>Contribute</a>
      <details>
        <summary class="{more_active}">More</summary>
        <div class="more-menu">
          <a href="/military.html"{cls('military')}>Military Service</a>
          <a href="/open-questions.html"{cls('open-questions')}>Open Questions</a>
          <a href="/sources.html"{cls('sources')}>Sources &amp; Methodology</a>
          <a href="/">Home</a>
        </div>
      </details>
    </nav>
  </div>
</header>
"""


def footer():
    return """<footer class="site-footer">
  <div class="shell">
    <p>The Quesenberry &amp; Harvey Family History — a private record assembled from public sources for the descendants of Lonnie Olin Quesenberry &amp; Ruth Garland Harvey.</p>
    <p class="muted">Some generations remain incomplete. <a href="/sources.html">See sources and methodology.</a> Last built from <code>data/people.json</code>.</p>
  </div>
</footer>
</body>
</html>"""


# ---- person page (refined per redesign brief §VI) ---------------------------

# Major American-history events for the "In their lifetime..." strip
HISTORY_EVENTS = [
    (1607, "Jamestown founded"),
    (1620, "Mayflower lands"),
    (1675, "King Philip's War"),
    (1718, "New Orleans founded"),
    (1733, "Georgia colony established"),
    (1754, "French & Indian War begins"),
    (1763, "End of Seven Years' War"),
    (1775, "American Revolution begins"),
    (1776, "Declaration of Independence"),
    (1783, "Treaty of Paris ends Revolution"),
    (1789, "Washington becomes first President"),
    (1803, "Louisiana Purchase"),
    (1812, "War of 1812 begins"),
    (1831, "Floyd County, VA formed"),
    (1846, "U.S.–Mexican War begins"),
    (1860, "Lincoln elected"),
    (1861, "Civil War begins"),
    (1865, "Civil War ends; Lincoln assassinated"),
    (1869, "Transcontinental Railroad completed"),
    (1898, "Spanish-American War"),
    (1903, "Wright Brothers fly at Kitty Hawk"),
    (1914, "World War I begins"),
    (1918, "WWI ends; Spanish flu pandemic"),
    (1920, "Women win the vote"),
    (1929, "Stock market crash; Great Depression"),
    (1941, "Pearl Harbor; U.S. enters WWII"),
    (1945, "WWII ends"),
    (1954, "Brown v. Board of Education"),
    (1963, "Kennedy assassinated"),
    (1969, "Apollo 11 lands on the Moon"),
    (1989, "Berlin Wall falls"),
    (2001, "September 11 attacks"),
]


def parse_year(date_str):
    """Pull out a 4-digit year from a date string like '15 January 1867' or '1748'."""
    if not date_str:
        return None
    m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(date_str))
    return int(m.group(1)) if m else None


def lifespan_years(p):
    """Return (birth_year, death_year) ints if available."""
    by = parse_year(p.get("birth"))
    dy = parse_year(p.get("death"))
    # also try lifespan field "1842–1898"
    if not by or not dy:
        ls = p.get("lifespan", "")
        m = re.search(r"(\d{4})\s*[–-]\s*(\d{4})", ls)
        if m:
            by = by or int(m.group(1))
            dy = dy or int(m.group(2))
    return by, dy


def archival_stamp(verified):
    """The wax-stamp/postmark style verification badge."""
    labels = {
        "documented":   ("Documented",   "stamp-documented"),
        "partial":      ("Partially documented",     "stamp-partial"),
        "tradition":    ("Family tradition",         "stamp-tradition"),
    }
    if verified in labels:
        text, cls = labels[verified]
        return f'<span class="archival-stamp {cls}">{text}</span>'
    return '<span class="archival-stamp stamp-undocumented">Not yet documented</span>'


def mini_tree(p):
    """Render the 'where they sit' ASCII-style mini family tree.
    Format:
        Parents  →  Person (this page)  →  Children
    Walks one generation up and one down.
    """
    name_short = p["name"].split(",")[0]
    parents = []
    if "father" in p and p["father"] in PEOPLE:
        parents.append(PEOPLE[p["father"]])
    if "mother" in p and p["mother"] in PEOPLE:
        parents.append(PEOPLE[p["mother"]])
    spouse = PEOPLE.get(p.get("spouse"))
    children = [PEOPLE[c] for c in p.get("children", []) if c in PEOPLE]

    lines = []
    if parents:
        for par in parents:
            lines.append(f'  <a href="/people/{par["id"]}.html">{par["name"]}</a>  ({par.get("lifespan","")})')
        lines.append("           │")
        lines.append("           ▼")
    person_line = f'  <span class="you">{name_short}</span>  ({p.get("lifespan","")})'
    if spouse:
        person_line += f'  ⚭  <a href="/people/{spouse["id"]}.html">{spouse["name"]}</a>'
    lines.append(person_line)
    if children:
        lines.append("           │")
        lines.append("           ▼")
        for ch in children:
            lines.append(f'  <a href="/people/{ch["id"]}.html">{ch["name"]}</a>  ({ch.get("lifespan","")})')
    if not (parents or children):
        return ""
    return f'<div class="mini-tree">{chr(10).join(lines)}</div>'


def lifetime_strip(p):
    """The 'In their lifetime...' horizontal historical-context strip.
    Picks 3-4 major American events that occurred during their life."""
    by, dy = lifespan_years(p)
    if not by:
        return ""
    if not dy:
        dy = by + 70  # estimate
    events_in_life = [(yr, ev) for yr, ev in HISTORY_EVENTS if by <= yr <= dy]
    if len(events_in_life) > 4:
        # pick 4 spread across life
        step = len(events_in_life) / 4
        events_in_life = [events_in_life[int(i*step)] for i in range(4)]
    events_html = ""
    for yr, ev in events_in_life:
        events_html += f'<div class="lifetime-event"><span class="yr">{yr}</span><span class="ev">{ev}</span></div>'
    if not events_html:
        events_html = f'<div class="lifetime-event"><span class="ev" style="grid-column:1/-1;text-align:center;">A quieter age, between the great American events.</span></div>'
    start_lbl = f'<span class="lbl">{by}</span>'
    end_lbl = f'<span class="lbl">{dy if parse_year(p.get("death")) else "—"}</span>'
    return f"""<aside class="lifetime-strip">
  <h3>In their lifetime…</h3>
  <div class="lifetime-axis">
    <div class="line"></div>
    <div class="endpoint start">{start_lbl}</div>
    <div class="endpoint end">{end_lbl}</div>
  </div>
  <div class="lifetime-events">{events_html}</div>
</aside>"""


def prev_next(p):
    """Find previous & next ancestor in the same branch by generation order."""
    branch = p.get("branch")
    if not branch:
        return ""
    siblings = [
        x for x in PEOPLE.values()
        if x.get("branch") == branch
    ]
    # sort by generation (1 = closest, higher = older)
    def gen_key(x):
        g = x.get("generation", 99)
        if isinstance(g, int):
            return g
        return 99
    siblings.sort(key=gen_key)
    ids = [x["id"] for x in siblings]
    try:
        idx = ids.index(p["id"])
    except ValueError:
        return ""
    prev_p = siblings[idx-1] if idx > 0 else None
    next_p = siblings[idx+1] if idx < len(siblings)-1 else None
    prev_html = ""
    next_html = ""
    if prev_p:
        prev_html = f'''<a class="prev" href="/people/{prev_p["id"]}.html">
          <span class="lbl">← Previous (closer to us)</span>
          <span class="nm">{prev_p["name"]}</span>
        </a>'''
    else:
        prev_html = '<span></span>'
    if next_p:
        next_html = f'''<a class="next" href="/people/{next_p["id"]}.html">
          <span class="lbl">Further back →</span>
          <span class="nm">{next_p["name"]}</span>
        </a>'''
    else:
        next_html = '<span></span>'
    return f'<nav class="prev-next">{prev_html}{next_html}</nav>'


def render_person_page(p):
    name = p["name"]
    lifespan = safe(p, "lifespan", "")
    epitaph = safe(p, "epitaph")
    birth = safe(p, "birth")
    birth_place = safe(p, "birthPlace")
    death = safe(p, "death")
    death_place = safe(p, "deathPlace")
    burial = safe(p, "burial")

    # facts card
    facts_dl = ""
    facts = p.get("facts", {})
    for k, v in facts.items():
        facts_dl += f"<dt>{k}</dt><dd>{v}</dd>"

    relations = ""
    if "father" in p or "mother" in p:
        relations += "<dt>Parents</dt><dd class='relations'>"
        if "father" in p: relations += person_link(p["father"]) + "<br>"
        if "mother" in p: relations += person_link(p["mother"])
        relations += "</dd>"
    if "spouse" in p:
        relations += f"<dt>Spouse</dt><dd class='relations'>{person_link(p['spouse'])}</dd>"
    if p.get("children"):
        relations += "<dt>Children</dt><dd class='relations'>"
        for c in p["children"]:
            relations += person_link(c) + "<br>"
        relations += "</dd>"

    location_block = ""
    if birth or birth_place:
        location_block += f"<dt>Born</dt><dd>{birth}{', ' if birth and birth_place else ''}{birth_place}</dd>"
    if death or death_place:
        location_block += f"<dt>Died</dt><dd>{death}{', ' if death and death_place else ''}{death_place}</dd>"
    if burial:
        location_block += f"<dt>Buried</dt><dd>{burial}</dd>"
    if p.get("marriedDate"):
        md = p["marriedDate"]
        mp = safe(p, "marriedPlace")
        location_block += f"<dt>Married</dt><dd>{md}{', ' if md and mp else ''}{mp}</dd>"

    # narrative — first paragraph gets dropcap
    paragraphs = p.get("narrative", [])
    body_html = ""
    for i, para in enumerate(paragraphs):
        cls = ' class="dropcap"' if i == 0 else ""
        body_html += f"<p{cls}>{md_to_html(para)}</p>\n"

    # Military as flag-red index card (if present)
    military_card = ""
    if "military" in p:
        military_card = f'''<aside class="index-card" style="border-left-color: var(--flag-red);">
  <span class="label" style="color: var(--flag-red);">Military Service</span>
  {p["military"]}
</aside>'''

    # Sources from facts dict — pull any URL-bearing entries into catalogue cards
    catalogue_html = ""
    cat_items = []
    for k, v in facts.items():
        if "<a href" in str(v):
            cat_items.append((k, v))
    if cat_items:
        cards = ""
        for label, content in cat_items:
            cards += f'<div class="catalogue-card"><span class="cat-label">{label}</span>{content}</div>'
        catalogue_html = f'''<h2>Sources for this profile</h2>
<div class="catalogue-cards">{cards}</div>'''

    # Photos for this person — real entries from photos.json + placeholders
    pid = p["id"]
    person_photos = [ph for ph in PHOTOS if pid in ph.get("people", []) and not is_example_entry(ph)]
    if person_photos:
        photo_items = ""
        for ph in person_photos:
            photo_items += f'''<a class="photo-frame-thumb" href="/photographs.html#photo-{ph["id"]}">
              <img src="/img/archive/{ph["file"]}" alt="{ph.get("caption","")[:60]}" onerror="this.style.display='none'; this.parentElement.classList.add('photo-missing');">
              <div class="photo-missing-msg">/img/archive/{ph["file"]}</div>
              <p class="photo-thumb-caption">{ph.get("year","")} — {ph.get("caption","")[:80]}</p>
            </a>'''
        photos_html = f'''<h2>Photographs</h2>
<div class="photo-gallery">{photo_items}</div>'''
    else:
        photos_html = f'''<h2>Photographs</h2>
<div class="photo-gallery">
  <div class="photo-empty">No photographs of {name.split(",")[0]} on file yet</div>
  <div class="photo-empty">If you have one, <a href="mailto:mike@cgcocktails.com?subject=Photo of {name}">share it →</a></div>
</div>'''

    # Stories & heirlooms tied to this person
    person_stories = [s for s in STORIES if pid in s.get("people", []) and not is_example_entry(s)]
    person_heirlooms = [h for h in HEIRLOOMS if h.get("originId") == pid and not is_example_entry(h)]
    extras_html = ""
    if person_stories or person_heirlooms:
        extras_html = '<h2>From the Archive</h2><ul class="archive-links">'
        for s in person_stories:
            extras_html += f'<li>📖 <a href="/stories.html#story-{s["id"]}">{s["title"]}</a> <span class="muted">— story</span></li>'
        for h in person_heirlooms:
            extras_html += f'<li>🪶 <a href="/heirlooms.html#heirloom-{h["id"]}">{h["name"]}</a> <span class="muted">— {h.get("type","heirloom")}</span></li>'
        extras_html += "</ul>"

    # Submission CTA
    submission_html = f'''<aside class="submission-cta">
  <h3>Add to {name.split(",")[0].split("(")[0].strip()}'s page</h3>
  <p>Have a photograph, a letter, a recording of a story, a Bible flyleaf, a maiden name we don't yet have? Anything you can share helps fill in the next layer of this record.</p>
  <a class="cta-btn" href="mailto:mike@cgcocktails.com?subject=Contribution for {name.split(',')[0]}">Send a contribution</a>
</aside>'''

    branch_label = p.get('branch', '').title()
    gen_label = p.get('generation', '?')

    html = head(name)
    html += header(active=p.get("branch", ""))
    html += f"""
<section class="person-header">
  <div class="shell">
    <p class="section-eyebrow">{branch_label} Line — Generation {gen_label}</p>
    <h1>{name}</h1>
    <p class="lifespan">{lifespan}</p>
    {f'<p class="epitaph">{md_to_html(epitaph)}</p>' if epitaph else ''}
    <p style="margin-top: 1.4rem;">{archival_stamp(p.get("verified"))}</p>
  </div>
</section>

<section class="person-body">
  <div class="shell">
    <div class="person-grid">
      <article>
        {mini_tree(p)}
        {military_card}
        {body_html}
        {lifetime_strip(p)}
        {photos_html}
        {extras_html}
        {catalogue_html}
        {submission_html}
        {prev_next(p)}
      </article>
      <aside class="facts-card">
        <h4>Vital Record</h4>
        <dl>
          {location_block}
          {relations}
          {facts_dl}
        </dl>
      </aside>
    </div>
  </div>
</section>
"""
    html += footer()
    write(PEOPLE_DIR / f"{p['id']}.html", html)


# ---- branch page ------------------------------------------------------------

BRANCH_DEFS = {
    "quesenberry": {
        "title": "The Quesenberry Line",
        "subtitle": "Kent → Virginia → the Blue Ridge → the Carolina Piedmont",
        "intro": (
            "The Quesenberrys are an old American family — old enough that no one in America today is descended from a "
            "Quesenberry whose ancestor wasn't on a wooden ship from Kent in 1624. The line traces from sixteen-year-old "
            "Thomas Questenbury crossing to the Virginia colony, through nine generations of farmers, soldiers, and "
            "frontiersmen who pushed the family name from the Tidewater into the Blue Ridge mountains and finally over "
            "into the Carolina Piedmont where Lonnie Olin Quesenberry was born in 1920."
        ),
    },
    "harvey": {
        "title": "The Harvey Line",
        "subtitle": "An English Piedmont name, planted in the Guilford red clay",
        "intro": (
            "The Harvey surname is one of the great English names in colonial North America — derived from the Old Breton "
            "given name Hervé, brought to England by the Normans and to America by the great seventeenth-century Tidewater "
            "migrations. Carl Harvey's particular Harvey line, on the present record, surfaces in Guilford County, North "
            "Carolina, in the early twentieth century — but its roots reach back into the colonial Piedmont and almost "
            "certainly into the great wave of Quaker, Scots-Irish, and English settlers who came down the Great Wagon Road "
            "from Pennsylvania in the 1740s."
        ),
    },
    "mcmichael": {
        "title": "The McMichael Line",
        "subtitle": "A Scots-Irish name in the Deep River farms of Guilford County, North Carolina",
        "intro": (
            "McMichael (occasionally spelled McMicheal) is a Scots-Irish surname carried to America from Ulster in the "
            "eighteenth century. It is sometimes confused with the Highland Scottish surname Carmichael — and earlier "
            "research on this site mistakenly traced Geneva's line back to Archibald Carmichael of Lanarkshire. That "
            "line has now been retracted: Mike's Ancestry tree confirms the maiden name as McMichael. Geneva Esther "
            "McMicheal Harvey (1891–1971) was a daughter of William Franklin McMichael (1849–1941) of Deep River, "
            "Guilford County, North Carolina — and the McMichael line traces back through Piedmont North Carolina, with "
            "roots almost certainly in the Scots-Irish migrations down the Great Wagon Road from Pennsylvania in the "
            "eighteenth century."
        ),
    },
}

def render_branch_page(branch_key):
    branch = BRANCH_DEFS[branch_key]
    people_in_branch = [p for p in PEOPLE.values() if p.get("branch") == branch_key]
    people_in_branch.sort(key=lambda p: p.get("generation", 99) if isinstance(p.get("generation", 99), int) else 99)

    cards = ""
    for p in people_in_branch:
        cards += f"""<article class="card">
  <p class="dates">Generation {p.get('generation', '?')}</p>
  <h3>{p['name']}</h3>
  <p class="role">{p.get('lifespan', '')}</p>
  <p>{md_to_html(p.get('epitaph', ''))}</p>
  <a class="read-more" href="/people/{p['id']}.html">Read profile →</a>
</article>"""

    html = head(branch["title"])
    html += header(active=branch_key)
    html += f"""
<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">A Family Line</p>
    <h1>{branch['title']}</h1>
    <p class="lede">{branch['subtitle']}</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    <p class="dropcap">{branch['intro']}</p>
  </div>
</section>

<section>
  <div class="shell">
    <h2>Generations</h2>
    <div class="card-grid">
      {cards}
    </div>
  </div>
</section>
"""
    html += footer()
    write(BRANCH_DIR / f"{branch_key}.html", html)


# ---- homepage ---------------------------------------------------------------

def render_home():
    # Quick "who's who" cards for grandparents
    featured = ["lonnie-quesenberry", "ruth-harvey", "thomas-questenbury", "archibald-carmichael", "aaron-quisenberry", "william-henry-quesenberry"]
    feat_cards = ""
    for fid in featured:
        if fid not in PEOPLE: continue
        p = PEOPLE[fid]
        feat_cards += f"""<article class="card">
  <p class="dates">{p.get('lifespan','')}</p>
  <h3>{p['name']}</h3>
  <p>{md_to_html(p.get('epitaph',''))}</p>
  <a class="read-more" href="/people/{p['id']}.html">Read →</a>
</article>"""

    html = head("Home")
    html += header(active="home")
    html += f"""
<div class="hero-photo placeholder">
  <div class="photo-bg"></div>
  <div class="photo-vignette"></div>
  <div class="photo-caption">
    <p class="dates">An American Story · Four Centuries</p>
    <h1 class="name">{SITE['title']}</h1>
    <p class="epitaph">{SITE['tagline']}</p>
  </div>
</div>

<section style="padding-top: 2rem;">
  <div class="shell narrow">
    <aside id="on-this-day" class="on-this-day" hidden>
      <p class="section-eyebrow">On This Day</p>
      <h3 class="otd-date"></h3>
      <ul class="otd-list"></ul>
    </aside>
    <script>
      (function() {{
        fetch("/events.json")
          .then(function(r) {{ return r.json(); }})
          .then(function(data) {{
            var today = new Date();
            var key = String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
            var events = data[key];
            if (!events || !events.length) return;
            var box = document.getElementById('on-this-day');
            var monthName = today.toLocaleString('en-US', {{ month: 'long' }});
            box.querySelector('.otd-date').textContent = monthName + ' ' + today.getDate();
            var list = box.querySelector('.otd-list');
            events.sort(function(a,b){{return a.year-b.year;}});
            events.forEach(function(e) {{
              var li = document.createElement('li');
              var icon = e.type === 'birth' ? '✦' : e.type === 'death' ? '✝' : '⚭';
              li.innerHTML = '<span class="otd-icon">'+icon+'</span><span class="otd-yr">'+e.year+'</span> <a href="'+e.link+'">'+e.summary+'</a>';
              list.appendChild(li);
            }});
            box.hidden = false;
          }})
          .catch(function(){{ /* fail silently */ }});
      }})();
    </script>
  </div>
</section>

<section>
  <div class="shell narrow">
    <p class="dropcap">{md_to_html(SITE['intro'])}</p>
    <p>This site collects what is presently known of the ancestors of <a href="/people/lonnie-quesenberry.html">Lonnie Olin Quesenberry</a> (1920–2002) and <a href="/people/ruth-harvey.html">Ruth Garland Harvey Quesenberry</a> (1925–2016) — the maternal grandparents of the family for whom this record was made. From them the trail runs back through the Quesenberry, Slusher (Schlosser), Hylton, Harvey, and Carmichael families to colonial Virginia, the Palatinate Germany of the 1700s, the Highlands of Scotland, and Kent, England in the reign of King James I.</p>
    <p>Browse by family line, by generation, or by the names that recur — Eva, Archibald, Aaron, Thomas, John — across the centuries.</p>

    <hr class="flourish">
  </div>
</section>

<section>
  <div class="shell">
    <p class="section-eyebrow center" style="text-align:center;">A Visual Index</p>
    <h2 style="text-align:center; border:none;">The Family Tree at a Glance</h2>
    <p class="lede" style="margin: 0 auto 2rem; text-align:center;">Lonnie and Ruth at the top — and beneath them, four centuries of ancestors stretching back to colonial Virginia, Highland Scotland, and Palatinate Germany.</p>
    <div style="text-align:center;">
      <a href="/tree.html" class="cta-btn" style="display:inline-block; font-family: var(--voice-caps); letter-spacing: 0.22em; text-transform: uppercase; font-size: 0.85rem; padding: 0.8em 1.6em; background: var(--rust); color: var(--paper); text-decoration: none; border: 1px solid var(--rust);">Open the family tree →</a>
    </div>
  </div>
</section>

<section>
  <div class="shell">
    <p class="section-eyebrow center" style="text-align:center;">Where to Begin</p>
    <h2 style="text-align:center; border:none;">Five Doorways into the Story</h2>
    <div class="card-grid">
      <article class="card">
        <p class="dates">The People</p>
        <h3>Lonnie &amp; Ruth</h3>
        <p>Begin with the maternal grandparents — the two lives from which the whole tree grows backward.</p>
        <a class="read-more" href="/people/lonnie-quesenberry.html">Lonnie →</a>
        &nbsp;
        <a class="read-more" href="/people/ruth-harvey.html">Ruth →</a>
      </article>
      <article class="card">
        <p class="dates">The Three Lines</p>
        <h3>The branches</h3>
        <p><a href="/branches/quesenberry.html">Quesenberry</a> from Kent in 1624 · <a href="/branches/harvey.html">Harvey</a> from the colonial Piedmont · <a href="/branches/carmichael.html">Carmichael</a> from Highland Scotland in 1775.</p>
      </article>
      <article class="card">
        <p class="dates">Service to Country</p>
        <h3>Military &amp; the Patriots</h3>
        <p>Two verified DAR Patriots, one family that sent nine sons to the Confederate Army, and the WWII generation. <a href="/military.html">Read →</a></p>
      </article>
      <article class="card">
        <p class="dates">Four Centuries</p>
        <h3>Timeline</h3>
        <p>Family events set against the spine of American history — from Jamestown to High Point. <a href="/timeline.html">View →</a></p>
      </article>
      <article class="card">
        <p class="dates">Methodology</p>
        <h3>Sources &amp; the Honest Gaps</h3>
        <p>What's verified, what's tradition, and what still waits in a courthouse basement. <a href="/sources.html">See sources →</a></p>
      </article>
    </div>
  </div>
</section>

<section>
  <div class="shell">
    <p class="section-eyebrow center" style="text-align:center;">Featured Ancestors</p>
    <h2 style="text-align:center; border:none;">A Few of the Voices</h2>
    <div class="card-grid">
      {feat_cards}
    </div>
  </div>
</section>

<section>
  <div class="shell narrow">
    <blockquote class="pullquote">
      Every American family carries an Atlantic crossing somewhere in its memory. For the Quesenberrys it was a sixteen-year-old boy from Kent in 1624. For the Carmichaels it was a Lanarkshire man on his twenty-first birthday in 1775. For the Slushers it was a Palatine German on the Great Wagon Road in the 1750s. The story of this family is the story of those crossings.
      <cite>— Editorial preface</cite>
    </blockquote>
  </div>
</section>
"""
    html += footer()
    write(PUBLIC / "index.html", html)


# ---- tree.json (data feed for the interactive tree page) -------------------

# Hard-coded geocodes for places that recur in this family record.
# Keys are case-insensitive substrings — matched in order, first hit wins.
PLACE_GEO = [
    ("bromley", (51.4045, 0.0142, "Bromley, Kent, England")),
    ("canterbury", (51.2802, 1.0789, "Canterbury, Kent, England")),
    ("kent, england", (51.2787, 0.5217, "Kent, England")),
    ("larne", (54.8479, -5.8068, "Larne, County Antrim, Ulster")),
    ("lanark", (55.6736, -3.7790, "Lanark, Lanarkshire, Scotland")),
    ("lancaster county, pennsylvania", (40.0379, -76.3055, "Lancaster County, Pennsylvania")),
    ("king george county", (38.2715, -77.1869, "King George County, Virginia")),
    ("caroline county, virginia", (38.0265, -77.3464, "Caroline County, Virginia")),
    ("orange county, virginia", (38.2470, -78.1116, "Orange County, Virginia")),
    ("st. thomas parish, orange county", (38.2470, -78.1116, "St. Thomas Parish, Orange County, Virginia")),
    ("westmoreland county", (38.1098, -76.7969, "Westmoreland County, Virginia")),
    ("montgomery county", (37.1737, -80.4084, "Montgomery County, Virginia")),
    ("floyd county", (36.9314, -80.3781, "Floyd County, Virginia")),
    ("greasy creek", (36.9314, -80.3781, "Greasy Creek, Floyd County, Virginia")),
    ("indian valley", (36.9764, -80.4798, "Indian Valley, Floyd County, Virginia")),
    ("wythe county", (36.9180, -81.0840, "Wythe County, Virginia")),
    ("glendale", (33.5387, -112.1860, "Glendale, Arizona Territory")),
    ("wilmington, north carolina", (34.2257, -77.9447, "Wilmington, North Carolina")),
    ("wilmington, nc", (34.2257, -77.9447, "Wilmington, North Carolina")),
    ("forsyth county", (36.1320, -80.2632, "Forsyth County, North Carolina")),
    ("stokes county", (36.4017, -80.2403, "Stokes County, North Carolina")),
    ("stanleyville", (36.2024, -80.2467, "Stanleyville, Forsyth County, North Carolina")),
    ("colfax", (36.1051, -79.9859, "Colfax, Guilford County, North Carolina")),
    ("guilford county", (36.0807, -79.7889, "Guilford County, North Carolina")),
    ("greensboro", (36.0726, -79.7920, "Greensboro, North Carolina")),
    ("kernersville", (36.1198, -80.0739, "Kernersville, Forsyth County, North Carolina")),
    ("high point", (35.9557, -80.0053, "High Point, Guilford County, North Carolina")),
    ("thomasville", (35.8826, -80.0820, "Thomasville, Davidson County, North Carolina")),
    ("davidson county", (35.7920, -80.2120, "Davidson County, North Carolina")),
    ("north carolina", (35.7596, -79.0193, "North Carolina")),
    ("virginia", (37.4316, -78.6569, "Virginia")),
    ("pennsylvania", (41.2033, -77.1945, "Pennsylvania")),
    ("scotland", (56.4907, -4.2026, "Scotland")),
    ("england", (52.3555, -1.1743, "England")),

    # Phase 6 — MyHeritage Cumberland Gap additions (May 2026)
    ("chancellorsville", (38.3094, -77.6404, "Chancellorsville Battlefield, Spotsylvania County, Virginia")),
    ("spotsylvania", (38.2007, -77.5994, "Spotsylvania County, Virginia")),
    ("jonesville", (36.6873, -83.1102, "Jonesville, Lee County, Virginia")),
    ("lee county, virginia", (36.7061, -83.1304, "Lee County, Virginia")),
    ("lee, virginia", (36.7061, -83.1304, "Lee County, Virginia")),
    ("washington county, virginia", (36.7184, -81.9667, "Washington County, Virginia")),
    ("washington, virginia", (36.7184, -81.9667, "Washington County, Virginia")),
    ("hawkins county, tennessee", (36.4434, -83.0017, "Hawkins County, Tennessee")),
    ("hawkins, tennessee", (36.4434, -83.0017, "Hawkins County, Tennessee")),
    ("hancock county, tennessee", (36.5395, -83.2218, "Hancock County, Tennessee")),
    ("hancock, tennessee", (36.5395, -83.2218, "Hancock County, Tennessee")),
    ("claiborne county, tennessee", (36.5101, -83.6557, "Claiborne County, Tennessee")),
    ("claiborne, tennessee", (36.5101, -83.6557, "Claiborne County, Tennessee")),
    ("yokum station", (36.7061, -83.1304, "Yokum Station District, Lee County, Virginia")),
    ("dickenson", (37.1407, -82.3479, "Dickenson County, Virginia")),
    ("russell county, virginia", (36.9347, -81.9617, "Russell County, Virginia")),
    ("russell, virginia", (36.9347, -81.9617, "Russell County, Virginia")),
    ("wise county, virginia", (36.9745, -82.6243, "Wise County, Virginia")),
    ("norton, wise", (36.9337, -82.6293, "Norton, Wise County, Virginia")),
    ("portsmouth, virginia", (36.8354, -76.2983, "Portsmouth, Virginia")),
    ("charlottesville", (38.0293, -78.4767, "Charlottesville, Virginia")),
    ("johns creek", (37.5043, -80.2189, "Johns Creek, Craig County, Virginia")),
    ("craig county, virginia", (37.4773, -80.2025, "Craig County, Virginia")),
    ("montgomery county, virginia", (37.1737, -80.4084, "Montgomery County, Virginia")),
    ("blacksburg", (37.2296, -80.4139, "Blacksburg, Montgomery County, Virginia")),
    ("rock island, illinois", (41.5095, -90.5787, "Rock Island Confederate POW Camp, Illinois")),
    ("rock island", (41.5095, -90.5787, "Rock Island, Illinois")),
    ("alamance", (36.0418, -79.4225, "Alamance County, North Carolina")),
    ("rockingham county, north carolina", (36.3992, -79.7780, "Rockingham County, North Carolina")),
    ("orange county, north carolina", (36.0610, -79.1198, "Orange County, North Carolina")),
    ("rowan county, north carolina", (35.6402, -80.5249, "Rowan County, North Carolina")),
    ("chester county, pennsylvania", (39.9634, -75.7484, "Chester County, Pennsylvania")),
    ("chester, pennsylvania", (39.9634, -75.7484, "Chester County, Pennsylvania")),
    ("chadds ford", (39.8718, -75.5919, "Chadds Ford, Chester County, Pennsylvania")),
    ("concord, pennsylvania", (39.8809, -75.5497, "Concord, Pennsylvania")),
    ("kennett township", (39.8237, -75.7090, "Kennett Township, Chester County, Pennsylvania")),
    ("hanover county, virginia", (37.7589, -77.4915, "Hanover County, Virginia")),
    ("cedar creek, hanover", (37.7589, -77.4915, "Cedar Creek, Hanover County, Virginia")),
    ("yadkin", (36.2048, -80.6601, "Yadkin, Stokes County, North Carolina")),
    ("graham, alamance", (36.0654, -79.3997, "Graham, Alamance County, North Carolina")),
    ("izard county, arkansas", (36.0941, -91.9007, "Izard County, Arkansas")),
    ("ben hur, lee", (36.7061, -83.1304, "Ben Hur, Lee County, Virginia")),

    # Phase 5 — Ancestry-research additions (May 2026)
    ("kingsport", (36.5484, -82.5618, "Kingsport, Sullivan County, Tennessee")),
    ("sullivan county, tennessee", (36.5070, -82.4663, "Sullivan County, Tennessee")),
    ("tennessee", (35.7478, -86.6923, "Tennessee")),
    ("bowers hill", (36.7818, -76.4138, "Bowers Hill, Norfolk, Virginia")),
    ("western branch", (36.8167, -76.4111, "Western Branch, Norfolk, Virginia")),
    ("norfolk, virginia", (36.8508, -76.2859, "Norfolk, Virginia")),
    ("norfolk", (36.8508, -76.2859, "Norfolk, Virginia")),
    ("deep river", (36.0001, -79.9420, "Deep River, Guilford County, North Carolina")),
    ("tobaccoville", (36.2587, -80.3548, "Tobaccoville, Forsyth County, North Carolina")),
    ("winston-salem", (36.0999, -80.2442, "Winston-Salem, Forsyth County, North Carolina")),

    # Phase 7 — MyHeritage record-match deep dive (May 18, 2026)
    ("edinburgh", (55.9533, -3.1883, "Edinburgh, Midlothian, Scotland")),
    ("midlothian, scotland", (55.8714, -3.0701, "Midlothian, Scotland")),
    ("bilston", (52.5664, -2.0747, "Bilston, Staffordshire, England")),
    ("staffordshire", (52.8793, -2.0573, "Staffordshire, England")),
    ("bruce, guilford", (35.9943, -79.9412, "Bruce, Guilford County, North Carolina")),
    ("springfield friends", (35.9968, -79.9587, "Springfield Friends Meeting, Guilford County, North Carolina")),
    ("forsyth, north carolina", (36.1320, -80.2632, "Forsyth County, North Carolina")),
    ("henrico", (37.5407, -77.4360, "Henrico County, Virginia (colonial)")),
    ("new garden", (36.0918, -79.8336, "New Garden Friends Meeting, Guilford County, North Carolina")),
]


def geocode(place):
    """Match a free-text place name to a (lat, lng, label) — or None."""
    if not place:
        return None
    pl = place.lower()
    for needle, geo in PLACE_GEO:
        if needle in pl:
            return geo
    return None


def render_tree_json():
    """Emit a denormalized JSON for the interactive tree page (D3 + Leaflet)."""
    out = {
        "site": SITE,
        "people": [],
    }
    for p in PEOPLE.values():
        by, dy = lifespan_years(p)
        birth_geo = geocode(p.get("birthPlace", ""))
        death_geo = geocode(p.get("deathPlace", ""))
        burial_geo = geocode(p.get("burial", ""))
        out["people"].append({
            "id": p["id"],
            "name": p["name"],
            "lifespan": p.get("lifespan", ""),
            "birth": p.get("birth", ""),
            "birthPlace": p.get("birthPlace", ""),
            "death": p.get("death", ""),
            "deathPlace": p.get("deathPlace", ""),
            "burial": p.get("burial", ""),
            "branch": p.get("branch", ""),
            "generation": p.get("generation"),
            "father": p.get("father"),
            "mother": p.get("mother"),
            "spouse": p.get("spouse"),
            "children": p.get("children", []),
            "verified": p.get("verified", ""),
            "epitaph": p.get("epitaph", ""),
            "military": p.get("military"),
            "birthYear": by,
            "deathYear": dy,
            "birthGeo": {"lat": birth_geo[0], "lng": birth_geo[1], "label": birth_geo[2]} if birth_geo else None,
            "deathGeo": {"lat": death_geo[0], "lng": death_geo[1], "label": death_geo[2]} if death_geo else None,
            "burialGeo": {"lat": burial_geo[0], "lng": burial_geo[1], "label": burial_geo[2]} if burial_geo else None,
        })
    write(PUBLIC / "tree.json", json.dumps(out, indent=2))


# ---- tree page (interactive: pedigree / timeline / map) --------------------

def render_tree():
    """Build an interactive 3-view tree page that consumes /tree.json."""

    body = """<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">A Visual Index</p>
    <h1>The Family Tree</h1>
    <p class="lede">Three views of the same family — pedigree, timeline, and migration map. Switch among them; clicking a name in any view focuses that person across all three.</p>
  </div>
</section>

<section style="padding-top: 1rem;">
  <div class="shell">
    <div class="tree-controls">
      <div class="view-tabs" role="tablist">
        <button data-view="pedigree" class="view-tab active" role="tab" aria-selected="true">Pedigree</button>
        <button data-view="timeline" class="view-tab" role="tab" aria-selected="false">Timeline</button>
        <button data-view="map"      class="view-tab" role="tab" aria-selected="false">Migration Map</button>
      </div>
      <div class="search-wrap">
        <input id="search" type="text" placeholder="Search a name…" autocomplete="off" />
        <ul id="search-results" class="search-results" hidden></ul>
      </div>
    </div>

    <div class="tree-layout">
      <div class="tree-stage">
        <div id="view-pedigree" class="view active"></div>
        <div id="view-timeline" class="view"></div>
        <div id="view-map"      class="view"></div>
      </div>
      <aside id="side-panel" class="side-panel">
        <p class="muted">Click any name to focus on a person.</p>
      </aside>
    </div>

    <p class="muted center" style="margin-top: 1.5rem;">All three views share one focused person. Use the search box to jump to anyone in the family by name.</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    <h2>How to read these views</h2>
    <p><strong>Pedigree.</strong> The classic upside-down tree: Lonnie and Ruth at the top, their parents below, and so on backward in time. Branches are color-coded — Quesenberry russet, Harvey forest, Carmichael gold. Lines connect children to parents.</p>
    <p><strong>Timeline.</strong> Each ancestor's life as a horizontal bar across four centuries — from Thomas Questenbury's birth in 1608 to Ruth's death in 2016. The shape of the family line becomes obvious at a glance: long lives, the gap of the Civil War, the consolidation in the Carolinas in the twentieth century.</p>
    <p><strong>Migration Map.</strong> The places that mattered, mapped and connected: Kent to Virginia in 1624, Larne to Wilmington in 1775, Lancaster County PA south down the Wagon Road, the Blue Ridge into the Carolina Piedmont. The story of this family is, fundamentally, a story of crossings.</p>
  </div>
</section>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="/js/tree.js" defer></script>"""

    html = head("Family Tree") + header(active="tree") + body + footer()
    write(PUBLIC / "tree.html", html)


# ---- timeline ---------------------------------------------------------------

TIMELINE_EVENTS = [
    ("1607", "Jamestown founded — the English colony of Virginia opens for business."),
    ("1608", "Thomas Questenbury born in Bromley, Kent, England."),
    ("1624", "<strong>The Atlantic Crossing.</strong> Thomas Questenbury, age 16, arrives in Virginia."),
    ("1627", "John Quisenberry born in colonial Virginia — the first American-born of the line."),
    ("1672", "Thomas Questenbury dies in Canterbury, having returned to England in old age."),
    ("1717", "John Quisenberry dies in Westmoreland County, Virginia, at about age 90."),
    ("1725", "Aaron Quisenberry Sr. born, Caroline County, Virginia."),
    ("1741", "Aaron Quisenberry, age 16, marries Joyce Gayle Dudley in King George County."),
    ("1748", "George Quesenberry born in Orange County, Virginia."),
    ("1754", "<strong>Highland Birth.</strong> Archibald Carmichael born in Lanark, Scotland — exactly 21 years before he sails for America."),
    ("1775–1781", "<strong>American Revolution.</strong> George Quesenberry serves with the Montgomery County, Virginia Militia. Aaron Quisenberry Sr. furnishes beef from his Orange County farm to the Continental Army — an act for which he is later listed as a DAR & SAR Patriot Ancestor."),
    ("4 Sep 1775", "<strong>The Second Atlantic Crossing.</strong> On his 21st birthday, Archibald Carmichael sails from Larne aboard the <em>Jupiter of Larne</em> for Wilmington, North Carolina."),
    ("1795", "Aaron Quisenberry Sr. dies in St. Thomas Parish, Orange County, Virginia."),
    ("1812", "George Quesenberry dies in Floyd County, Virginia, in the year America declares its second war on Britain."),
    ("1827", "Archibald Carmichael dies in Forsyth County, North Carolina."),
    ("1831", "Floyd County, Virginia is formed from Montgomery County."),
    ("1838", "Eva Jane Slusher born in Floyd County, Virginia."),
    ("1841", "William Henry Quesenberry born in Indian Valley, Floyd County, Virginia."),
    ("1853", "John Quesenberry Sr. dies in Wythe County, Virginia."),
    ("1861–1865", "<strong>The Civil War.</strong> Multiple Quesenberry men of Floyd County serve in the Confederate Army — including Frederick Quesenberry of the 54th Virginia Infantry. Family tradition holds that nine sons of John Quesenberry Sr.'s line served in all."),
    ("1867", "William Henry Quesenberry marries Eva Jane Slusher — barely two years after Appomattox."),
    ("1898", "William Henry Quesenberry dies in Glendale, Arizona Territory — having migrated west in old age."),
    ("1920", "<strong>Lonnie Olin Quesenberry born in North Carolina.</strong>"),
    ("1925", "<strong>Ruth Garland Harvey born in Guilford County, North Carolina.</strong>"),
    ("1926", "Eva Jane Slusher Quesenberry dies, age 88."),
    ("1941–1945", "World War II. Lonnie Quesenberry comes of military age."),
    ("17 July 1948", "<strong>The Marriage.</strong> Lonnie marries Ruth in Greensboro, NC."),
    ("2002", "Lonnie Olin Quesenberry dies, age 82, at High Point, NC."),
    ("2016", "Ruth Garland Harvey Quesenberry dies, age 90, at High Point, NC. Three centuries and four months separate her from the boy who stepped off the ship in Virginia."),
]

def render_timeline():
    items = ""
    for year, event in TIMELINE_EVENTS:
        items += f'<li><span class="year">{year}</span><span class="event">{event}</span></li>\n'

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Four Centuries</p>
    <h1>A Family Timeline</h1>
    <p class="lede">From Jamestown to High Point — the family story set against the spine of American history.</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    <ol class="timeline">
      {items}
    </ol>
  </div>
</section>"""
    html = head("Timeline") + header(active="timeline") + body + footer()
    write(PUBLIC / "timeline.html", html)


# ---- military page ----------------------------------------------------------

def render_military():
    body = """<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Service to Country</p>
    <h1>Military Service</h1>
    <p class="lede">From the American Revolution to the Civil War to the Second World War — the soldiers in the family record.</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    <h2>The American Revolution — Two Verified Patriots</h2>

    <h3>Aaron Quisenberry Sr. (1725–1795) <span class="badge-military dar">DAR Patriot #A093307</span></h3>
    <p>Aaron Quisenberry of Orange County, Virginia is a <strong>verified Daughters of the American Revolution Patriot Ancestor, #A093307</strong>. His Revolutionary War service: he furnished beef from his Orange County farm to the Continental Army. He is also recognized by the National Society Sons of the American Revolution. Any descendant of Aaron Quisenberry — and the Quesenberry family has many thousands — is eligible for membership in the DAR or SAR through his line.</p>
    <p>Sources: <a href="https://services.dar.org/Public/DAR_Research/search_adb/">DAR Genealogical Research System</a>; <a href="https://www.wikitree.com/wiki/Quisenberry-38">WikiTree: Aaron Quisenberry Sr.</a>; <a href="https://www.findagrave.com/memorial/109976116/aaron-quisenberry">Find a Grave 109976116</a>.</p>

    <h3>Christopher Slusher / Schlosser (1757–1845) <span class="badge-military dar">DAR Patriot #A105465</span></h3>
    <p>The German-American great-grandfather of Eva Jane Slusher Quesenberry, Christopher Slusher (born <em>Schlosser</em> in Lancaster County, Pennsylvania) is a <strong>verified DAR Patriot Ancestor, #A105465</strong>, with documented Revolutionary War service from Pennsylvania. He later migrated south down the Great Wagon Road into Virginia, where he died in Floyd County at age 88. Through Eva Jane Slusher, this is a second verified DAR Patriot in the direct family line.</p>
    <p>Sources: <a href="https://services.dar.org/Public/DAR_Research/search_adb/">DAR Genealogical Research System</a>; <a href="https://www.geni.com/people/Christopher-Slusher-I/6000000003375740945">Geni: Christopher Slusher</a>.</p>

    <h3>George Quesenberry (1748–1812) <span class="badge-military">Montgomery Co. VA Militia</span></h3>
    <p>Aaron Quisenberry's son George served with the <strong>Montgomery County, Virginia Militia</strong> during the American Revolution — one of the western Virginia militia units that defended the frontier. Quesenberrys are recorded on Montgomery County militia muster rolls of the period. After the war he migrated into the Blue Ridge country that would, in 1831, become Floyd County.</p>
    <p>Source: <a href="https://www.wikitree.com/wiki/Quesenberry-12">WikiTree: George Quesenberry</a>.</p>

    <h2>The American Civil War</h2>

    <h3>The Nine Confederate Sons of John Quesenberry &amp; Nancy Hylton</h3>
    <p>The Quesenberry family of Floyd County, Virginia is, on documentary record, the <strong>only known American family to have sent nine sons into Confederate service</strong>. All nine were sons of John Quesenberry Sr. (1790–1853) and Nancy Hylton Quesenberry (1803 – aft. 1860) of Greasy Creek, Floyd County. John Sr. died in 1853 — eight years before the war began — and so it was Nancy who lived to see her nine sons march off in gray.</p>

    <p><strong>The nine sons:</strong></p>
    <ol>
      <li><strong>George Washington Quesenberry</strong> — 54th Virginia Infantry</li>
      <li><strong>Elijah Quesenberry</strong></li>
      <li><strong>Thomas Frederick Quesenberry</strong> — enlisted 16 September 1861, Company B, 54th Virginia Infantry</li>
      <li><strong>Archelaus Quesenberry</strong> (b. 26 May 1826) — died December 1863 during the war</li>
      <li><strong>Nathaniel Floyd Quesenberry</strong> — mustered into Co. D, 54th Virginia Infantry, 24 March 1862</li>
      <li><strong>John Quesenberry Jr.</strong></li>
      <li><strong>William Henry Clay Quesenberry</strong> (b. 10 January 1842) — survived the war, married Eva Jane Slusher 1867, eventually migrated to Arizona Territory and died at Glendale 1898</li>
      <li><strong>Amos Ballard Quesenberry</strong></li>
      <li><strong>James Montgomery Quesenberry</strong></li>
    </ol>

    <p>The 54th Virginia Infantry was raised primarily from the southwestern Virginia counties — Floyd, Carroll, Patrick, Pulaski, and Wythe — and fought through major engagements of the Western Theater, including Murfreesboro, Chickamauga, the Atlanta Campaign, and the final retreat through the Carolinas in 1865. The Company G of the 49th Virginia Infantry, which also included Quesenberrys, fought in the Eastern Theater.</p>

    <p>The <strong>Quesenberry Family Papers</strong> (1827–1913) at the Virginia Museum of History &amp; Culture in Richmond preserve the 1862 muster roll of Company G, 49th Virginia Infantry, along with family correspondence. A research visit there is the next step toward identifying every Quesenberry of any branch who served — and which of these brothers came home.</p>

    <p>Sources: <a href="https://www.wikitree.com/wiki/Quesenberry-5">WikiTree: John Quesenberry Sr.</a>; <a href="https://www.findagrave.com/memorial/120926374/john-quesenberry">Find a Grave 120926374</a>; <a href="https://www.findagrave.com/memorial/102756060/frederick-quesenberry">Find a Grave: Frederick Quesenberry 102756060</a>; <a href="https://www.findagrave.com/memorial/59785124/nathaniel-quesenberry">Find a Grave: Nathaniel Quesenberry 59785124</a>; <a href="https://virginiahistory.org/research/research-resources/guides-researchers/quesenberry-family-papers-rutherfoord-family-papers">Quesenberry Family Papers, VMHC</a>.</p>

    <h2>The World Wars</h2>

    <h3>Lonnie Olin Quesenberry (1920–2002) <span class="badge-military">WWII Generation — record not yet pulled</span></h3>
    <p>Lonnie Olin Quesenberry was 21 years old when the United States entered the Second World War. Like virtually every American man born in 1920, he was required to register for the draft, and a draft card almost certainly exists for him in the National Archives WWII Draft Registration Cards collection (FamilySearch Collection 1968530, also indexed on Ancestry.com and Fold3). The card has not yet been located in the publicly-searchable indexes, but the path to it is now well-defined: a family member with an Ancestry, FamilySearch, or Fold3 account can search the WWII Draft Cards collection for &quot;Lonnie Olin Quesenberry&quot; in North Carolina and almost certainly retrieve the card image. The card itself records date of registration, residence, employer, height, weight, complexion, and nearest relative.</p>

    <h2>Lines of inquiry that would expand this section</h2>
    <ul>
      <li>The complete <strong>Quesenberry Family Papers</strong> at the Virginia Museum of History &amp; Culture — including the full 1862 muster roll and any correspondence — would identify by name every Quesenberry son who served in the Confederate Army, including precise regiments, ranks, and post-war fates.</li>
      <li>The <strong>National Personnel Records Center</strong> in St. Louis holds the WWII draft and service records, including very likely Lonnie Olin Quesenberry's.</li>
      <li><strong>Floyd, Carroll, and Pulaski County</strong> Civil War rosters — many transcribed in the <em>Carroll County Chronicles</em> and similar local journals — would expand the picture for all the Quesenberry, Hylton, and Slusher men of the war years.</li>
      <li>The <strong>SAR and DAR application files</strong> at the Library in Washington, D.C., for Aaron Quisenberry and Christopher Slusher, contain the original verifying genealogical proof — useful both for joining the societies and for confirming the line back to colonial Virginia and Pennsylvania.</li>
    </ul>
  </div>
</section>"""
    html = head("Military Service") + header(active="military") + body + footer()
    write(PUBLIC / "military.html", html)


# ---- sources page -----------------------------------------------------------

def render_sources():
    body = """<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Methodology</p>
    <h1>Sources &amp; Notes</h1>
    <p class="lede">Every claim in this site can be traced back to a public source. Where evidence is incomplete, we say so plainly.</p>
  </div>
</section>

<section>
  <div class="shell narrow">

    <h2>Verification status — at a glance</h2>
    <p>Each ancestor profile on this site carries a small badge:</p>
    <ul>
      <li><span class="badge-verified">✓ Documented</span> — birth, death, parents, and key facts are confirmed in publicly accessible records (Find a Grave, obituaries, DAR/SAR registries, or census images).</li>
      <li><span class="badge-partial">◐ Partial</span> — the person is named in a documentary source but vital dates or parentage await further research (e.g., Floyd H. Quesenberry, Eva Quesenberry, Carl/Carol Harvey, Geneva Carmichael).</li>
      <li><span class="badge-tradition">○ Tradition</span> — the person appears in family trees but is not yet confirmed in primary records.</li>
    </ul>

    <h2>Primary sources used</h2>

    <h3>Direct family records</h3>
    <ul class="source-list">
      <li><a href="https://www.findagrave.com/memorial/157298614/lonnie-olin-quesenberry">Find a Grave 157298614</a> — Lonnie Olin Quesenberry (1920–2002)</li>
      <li><a href="https://www.findagrave.com/memorial/157298694/ruth-quesenberry">Find a Grave 157298694</a> — Ruth Garland Harvey Quesenberry (1925–2016) — full obituary text preserved</li>
      <li><a href="https://piercejeffersonfh.com/tribute/details/205865/Esther-Scott/obituary.html">Pierce-Jefferson Funeral Home obituary</a> — <strong>Esther Harvey Scott (1929–2021)</strong> — Ruth's sister; this obituary is the single richest documentary source for the Harvey side of the family, naming both parents (Carol &amp; Geneva Harvey), birth date and place (2 August 1929, Colfax NC), husband (Anderson L. Scott), wedding date (9 August 1947), and burial (Shady Grove Wesleyan Church Cemetery, Colfax)</li>
      <li><a href="https://ancestors.familysearch.org/en/G7JS-RHX/lonnie-olin-quesenberry-1920-2002">FamilySearch G7JS-RHX</a> — Lonnie Quesenberry (login required for the full tree)</li>
      <li><a href="https://ancestors.familysearch.org/en/G7J3-9BC/ruth-garland-harvey-1925-2016">FamilySearch G7J3-9BC</a> — Ruth Harvey (login required for the full tree)</li>
    </ul>

    <h3>Verified Revolutionary War service</h3>
    <ul class="source-list">
      <li><a href="https://services.dar.org/Public/DAR_Research/search_adb/">DAR Genealogical Research System</a> — Aaron Quisenberry Sr. is verified DAR Patriot Ancestor <strong>#A093307</strong></li>
      <li><a href="https://services.dar.org/Public/DAR_Research/search_adb/">DAR Genealogical Research System</a> — Christopher Slusher (Schlosser) is verified DAR Patriot Ancestor <strong>#A105465</strong></li>
      <li><a href="https://www.wikitree.com/wiki/Quisenberry-38">WikiTree: Aaron Quisenberry Sr.</a></li>
      <li><a href="https://www.geni.com/people/Christopher-Slusher-I/6000000003375740945">Geni: Christopher Slusher</a></li>
    </ul>

    <h3>Civil War — the nine Confederate sons</h3>
    <ul class="source-list">
      <li><a href="https://virginiahistory.org/research/research-resources/guides-researchers/quesenberry-family-papers-rutherfoord-family-papers">Quesenberry Family Papers (1827–1913), Virginia Museum of History &amp; Culture</a> — preserves the 1862 muster roll of Co. G, 49th Virginia Infantry, listing multiple Quesenberrys</li>
      <li><a href="https://www.findagrave.com/memorial/120926374/john-quesenberry">Find a Grave 120926374</a> — John Quesenberry Sr. (1790–1853), patriarch of the nine Confederate sons</li>
      <li><a href="https://www.findagrave.com/memorial/102756060/frederick-quesenberry">Find a Grave: Thomas Frederick Quesenberry</a> — Co. B, 54th VA Infantry</li>
      <li><a href="https://www.findagrave.com/memorial/59785124/nathaniel-quesenberry">Find a Grave: Nathaniel Floyd Quesenberry</a> — Co. D, 54th VA Infantry</li>
      <li><a href="https://www.familysearch.org/en/wiki/49th_Regiment,_Virginia_Infantry_-_Confederate">FamilySearch — 49th Virginia Infantry (Confederate)</a></li>
      <li><a href="https://sites.rootsweb.com/~vafloyd/BarbR_FCVAResearch/quesenberry_John_Nancy.htm">RootsWeb: John &amp; Nancy (Hylton) Quesenberry Family</a></li>
    </ul>

    <h3>Colonial American line — Quesenberry / Quisenberry / Questenbury</h3>
    <ul class="source-list">
      <li><a href="https://www.wikitree.com/wiki/Questenbury-1">WikiTree: Thomas Questenbury (1608–1672)</a> — the Kent-born immigrant of 1624</li>
      <li><a href="https://www.wikitree.com/wiki/Quisenberry-47">WikiTree: John Quisenberry (1627–1717)</a> — first American-born of the line</li>
      <li><a href="https://www.wikitree.com/wiki/Pope-456">WikiTree: Anne (Pope) Quisenberry</a> — wife of John, cousin of Anne Pope Washington</li>
      <li><a href="https://www.nps.gov/gewa/learn/historyculture/anne-pope-washington.htm">National Park Service: Anne Pope Washington (great-grandmother of George Washington)</a> — establishes the Pope kinship</li>
      <li><a href="https://www.wikitree.com/genealogy/QUESENBERRY">WikiTree Quesenberry profiles</a> — ~600 collaborative profiles</li>
      <li><a href="https://www.virtualjamestown.org/Muster/muster24.html">Virtual Jamestown 1624/5 Muster</a> — searchable index of early colonial Virginia</li>
    </ul>

    <h3>Carmichael line — Highland Scottish migration of 1775</h3>
    <ul class="source-list">
      <li><a href="https://www.wikitree.com/wiki/Carmichael-6">WikiTree: Archibald Carmichael Sr. (1754–1827)</a></li>
      <li><a href="http://www.old-new-orleans.com/Carmichaels_aboard_Jupiter_of_Larne.html">Carmichaels aboard the <em>Jupiter of Larne</em>, 4 September 1775</a> — passenger list with ages</li>
      <li><a href="https://tompaterson.co.uk/carmichael/Carmichael_Carolinas.html">Tom Paterson — Immigrant Carmichaels of the Carolinas</a></li>
      <li><a href="https://www.wikitree.com/wiki/Carmichael-273">WikiTree: Duncan Carmichael Jr.</a> (Archibald's brother, also in NC)</li>
    </ul>

    <h3>Slusher / Schlosser line — Pennsylvania-German colonial migration</h3>
    <ul class="source-list">
      <li><a href="https://www.geni.com/people/Christopher-Slusher-I/6000000003375740945">Geni: Christopher Slusher (Schlosser) (1757–1845)</a> — DAR Patriot, Pennsylvania service</li>
      <li><a href="https://www.geni.com/people/Eva-Jane-Hancock-Schlosser/6000000014982162794">Geni: Eve Hancock Schlosser (1761–1838)</a></li>
      <li><a href="https://www.wikitree.com/genealogy/SLUSHER">WikiTree Slusher genealogy</a></li>
    </ul>

    <h3>Local context &amp; geography</h3>
    <ul class="source-list">
      <li><a href="https://floydhistoricalsociety.org/mapping-the-settlers-and-first-landowners-in-floyd-county/">Floyd County, VA Historical Society — settlement maps</a></li>
      <li><a href="https://www.findagrave.com/cemetery/2235718/hoover-quesenberry-farm-cemetery">Hoover-Quesenberry Farm Cemetery, Indian Valley, Floyd County, VA</a></li>
      <li><a href="https://www.findagrave.com/cemetery/47706/holly-hill-memorial-park">Holly Hill Memorial Park, Thomasville, NC</a> — burial site of Lonnie &amp; Ruth</li>
      <li><a href="https://www.findagrave.com/cemetery/2176787/shady-grove-wesleyan-church-cemetery">Shady Grove Wesleyan Church Cemetery, Colfax, NC</a> — burial site of Esther; possibly of Carol/Carl &amp; Geneva Harvey</li>
      <li><a href="https://colfaxes.gcsnc.com/our-school/colfax-elementary-history">Colfax Elementary History (formerly Colfax High School)</a></li>
    </ul>

    <h2>What is well-documented</h2>
    <ul>
      <li>Lonnie and Ruth's exact birth/death/burial dates and locations.</li>
      <li>Ruth's sister Esther Harvey Scott — completely documented from her 2021 obituary.</li>
      <li>Both parents named on the Harvey side: <strong>Carol Harvey</strong> (per Esther's obituary) / <strong>Carl Harvey</strong> (per Ruth's obituary) and <strong>Geneva Carmichael Harvey</strong>.</li>
      <li>Lonnie's parents named: Floyd H. Quesenberry and Eva Quesenberry.</li>
      <li>The Quesenberry colonial line back to Thomas Questenbury (immigrant 1624).</li>
      <li>Aaron Quisenberry's DAR Patriot status (#A093307) — verified.</li>
      <li>Christopher Slusher's DAR Patriot status (#A105465) — verified.</li>
      <li>The nine Confederate sons of John Quesenberry &amp; Nancy Hylton — all named, with regimental affiliations partly documented.</li>
      <li>Anne Pope / Anne Pope Washington kinship — verified through NPS and corroborating Pope-family genealogies.</li>
      <li>Archibald Carmichael's 4 September 1775 emigration on the <em>Jupiter of Larne</em>, with passenger list confirming wife Mary and daughter Katherine.</li>
    </ul>

    <h2>What still needs further research</h2>
    <p>The honest gaps. These are the highest-priority next steps for any family member who picks up the trail:</p>
    <ol>
      <li><strong>Connect Floyd H. Quesenberry to the documented Quesenberry tree.</strong> The most likely link is to one of the nine Confederate sons of John Quesenberry &amp; Nancy Hylton — most plausibly through William Henry Clay Quesenberry's surviving children. The Floyd, Carroll, and Patrick County (VA) courthouse records, along with North Carolina marriage records 1900–1930, should close this gap.</li>
      <li><strong>Eva Quesenberry's maiden name.</strong> Marriage record between Floyd H. Quesenberry and Eva, possibly in Floyd County VA or Davidson County NC.</li>
      <li><strong>Carol/Carl Harvey's vital dates and parents.</strong> Best leads: Shady Grove Wesleyan Church Cemetery, Colfax (where Esther is buried — Carol may be there too); North Carolina Death Index 1908–2004; Guilford County Register of Deeds.</li>
      <li><strong>Geneva Carmichael Harvey's parentage.</strong> Once known, the next question is whether she descends from Archibald Carmichael of the <em>Jupiter of Larne</em>, or from one of the other Highland Carmichael families of the same Carolina migration.</li>
      <li><strong>Anderson L. Scott</strong> — Esther's husband. Forsyth County (Kernersville) records.</li>
      <li><strong>Phillip Olyn Quesenberry</strong> (Lonnie &amp; Ruth's son, d. 2015). High Point Enterprise obituary archive 2015 and Cumby Family Funeral Service records.</li>
      <li><strong>Lonnie Quesenberry's WWII Draft Card.</strong> FamilySearch Collection 1968530, indexed on Ancestry.com and Fold3. A family member with an Ancestry account can almost certainly retrieve the card image in five minutes.</li>
      <li><strong>The complete 1862 Quesenberry Confederate muster roll</strong> at the Virginia Museum of History &amp; Culture, Richmond — would identify by name every Quesenberry of any branch who served, with regiments and ranks.</li>
    </ol>

    <h2>How to extend this site</h2>
    <p>All content lives in a single human-readable JSON file at <code>data/people.json</code>. To add a new ancestor:</p>
    <ol>
      <li>Open <code>data/people.json</code>.</li>
      <li>Copy an existing person record and modify the fields.</li>
      <li>Add the new id to any parent's <code>children</code> array, and link via <code>father</code>, <code>mother</code>, or <code>spouse</code>.</li>
      <li>Set <code>verified</code> to <code>"documented"</code>, <code>"partial"</code>, or <code>"tradition"</code>.</li>
      <li>Run <code>python3 build.py</code> from the project root. New HTML pages appear in <code>public/</code>.</li>
      <li>Commit and push — Railway redeploys automatically.</li>
    </ol>

    <h2>A note on family memory</h2>
    <p>The richest sources of all — the photographs in shoeboxes, the family Bibles with names written in the flyleaf, the recorded memories of Lonnie and Ruth's still-living children and grandchildren — are not on the internet at all. Anyone in the family with access to those things can dramatically expand this record. The structure of this site is designed to absorb that material easily as it surfaces.</p>
  </div>
</section>"""
    html = head("Sources") + header(active="sources") + body + footer()
    write(PUBLIC / "sources.html", html)


# ---- main -------------------------------------------------------------------

# ============================================================
#   PHASE 3 — module renderers (Photographs, Stories, Places, Heirlooms)
# ============================================================

def empty_state_msg(thing, contribute_subject):
    """Render an inviting empty-state block when a module has no real entries yet."""
    return f"""<div class="empty-state">
  <p class="section-eyebrow">Awaiting Your Contribution</p>
  <h3>{thing}</h3>
  <p>This page exists to hold {thing.lower()} as they surface — from family albums, Bible flyleaves, recorded stories, deed boxes, and the memories of everyone who knew the people in this record.</p>
  <p>If you have something to share, send it along. We'll add it to the archive properly attributed.</p>
  <a class="cta-btn" href="mailto:mike@cgcocktails.com?subject={contribute_subject}">Contribute</a>
</div>"""


def is_example_entry(entry):
    """Return True if an entry's id starts with 'example-' so we can flag/dim it."""
    return str(entry.get("id", "")).startswith("example-")


def render_photographs():
    """Per brief: chronological wall, tagged with the people who appear."""
    real = [p for p in PHOTOS if not is_example_entry(p)]
    examples = [p for p in PHOTOS if is_example_entry(p)]

    cards = ""
    for ph in sorted(PHOTOS, key=lambda x: str(x.get("year", "9999"))):
        people_links = " · ".join(person_link(pid) for pid in ph.get("people", []))
        is_ex = is_example_entry(ph)
        ex_note = '<span class="badge-tradition" style="margin-bottom:0.6em;">Example placeholder</span>' if is_ex else ""
        img_block = f'''<div class="photo-frame">
            <img src="/img/archive/{ph["file"]}" alt="{ph["caption"][:80]}" onerror="this.style.display='none'; this.parentElement.classList.add('photo-missing');">
            <div class="photo-missing-msg">Image file not yet uploaded:<br><code>/img/archive/{ph["file"]}</code></div>
          </div>''' if ph.get("file") else ""
        cards += f"""<article class="photo-card">
          {img_block}
          <div class="photo-meta">
            {ex_note}
            <p class="dates">{ph.get("year", "")} · {ph.get("place", "")}</p>
            <p class="caption">{md_to_html(ph.get("caption", ""))}</p>
            {f'<p class="muted">In this image: {people_links}</p>' if people_links else ""}
            <p class="muted source">Source: {ph.get("source", "Unknown")}</p>
          </div>
        </article>"""

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">The Archive</p>
    <h1>Photograph Archive</h1>
    <p class="lede">A growing visual record — portraits, documents, places, heirlooms — arranged in time.</p>
  </div>
</section>

<section>
  <div class="shell">
    {empty_state_msg("Photographs and documents", "Photo for the family archive") if not real else ""}
    {f'<p class="muted center">Currently {len(real)} real entries and {len(examples)} placeholder example. Replace examples by editing <code>data/photos.json</code> and dropping image files into <code>public/img/archive/</code>.</p>' if cards else ""}
    <div class="photo-wall">{cards}</div>
  </div>
</section>"""

    html = head("Photograph Archive") + header(active="archive") + body + footer()
    write(PUBLIC / "photographs.html", html)


def render_stories():
    """Stories & oral histories — chronological, by year of events."""
    real = [s for s in STORIES if not is_example_entry(s)]
    examples = [s for s in STORIES if is_example_entry(s)]

    cards = ""
    for s in sorted(STORIES, key=lambda x: str(x.get("year", "9999"))):
        people_links = " · ".join(person_link(pid) for pid in s.get("people", []))
        is_ex = is_example_entry(s)
        ex_note = '<span class="badge-tradition">Example placeholder</span>' if is_ex else ""
        teller = s.get("teller", "Unknown teller")
        if s.get("tellerId"):
            teller = person_link(s["tellerId"])
        audio_block = ""
        if s.get("audio"):
            audio_block = f'<audio controls preload="none" src="{s["audio"]}" style="width:100%; margin-bottom:1rem;"></audio>'

        cards += f"""<article class="story-card">
          <header>
            {ex_note}
            <p class="dates">{s.get("year", "")} · {s.get("place", "")}</p>
            <h2>{s.get("title", "Untitled")}</h2>
            <p class="muted">As told by {teller}{f' · recorded {s["recorded"]}' if s.get("recorded") else ""}</p>
            {f'<p class="muted">About: {people_links}</p>' if people_links else ""}
          </header>
          {audio_block}
          <div class="story-body">{md_to_paragraphs(s.get("body", ""))}</div>
        </article>"""

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Voices</p>
    <h1>Stories &amp; Oral Histories</h1>
    <p class="lede">The things that didn't make it into a courthouse record — the stories told around kitchen tables, the recipes called out from memory, the sayings repeated until they became inheritance.</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    {empty_state_msg("Stories and oral histories", "Story for the family archive") if not real else ""}
    {f'<p class="muted center">Currently {len(real)} real stories and {len(examples)} placeholder example. To add one, edit <code>data/stories.json</code>.</p>' if cards else ""}
    <div class="story-stack">{cards}</div>
  </div>
</section>"""

    html = head("Stories & Oral Histories") + header(active="stories") + body + footer()
    write(PUBLIC / "stories.html", html)


def render_places():
    """Places & migration — the geographic spine of the family record."""
    cards = ""
    for pl in PLACES:
        people_links = " · ".join(person_link(pid) for pid in pl.get("people", []))
        geo = geocode(pl.get("id", "")) or geocode(pl.get("name", ""))
        coord_lbl = f'{geo[0]:.3f}, {geo[1]:.3f}' if geo else 'Coordinates not yet recorded'
        cards += f"""<article class="place-card" id="place-{pl["id"]}">
          <h2>{pl.get("name", "")}</h2>
          <p class="dates">📍 {coord_lbl}</p>
          <p class="lede">{md_to_html(pl.get("shortDescription", ""))}</p>
          <p>{md_to_html(pl.get("longDescription", ""))}</p>
          {f'<p class="muted">Family connections: {people_links}</p>' if people_links else ""}
        </article>
        <hr class="flourish">"""

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Geography of a Family</p>
    <h1>Places &amp; Migration</h1>
    <p class="lede">Each place that mattered — the parishes, county seats, ports, and farmsteads where the lives in this record were lived.</p>
  </div>
</section>

<section>
  <div class="shell">
    <p class="muted center">For the interactive map showing every birthplace and death-place plus migration arcs, see <a href="/tree.html">the tree page</a>'s Map view.</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    {cards if cards else empty_state_msg("Place histories", "Place note for the family archive")}
  </div>
</section>"""

    html = head("Places &amp; Migration") + header(active="places") + body + footer()
    write(PUBLIC / "places.html", html)


def render_heirlooms():
    """Heirlooms & recipes — the objects, recipes, songs, and sayings."""
    real = [h for h in HEIRLOOMS if not is_example_entry(h)]
    examples = [h for h in HEIRLOOMS if is_example_entry(h)]

    type_icons = {
        "recipe": "🥧", "object": "🪑", "document": "📜", "song": "♫",
        "saying": "❝", "medal": "🎖", "bible": "✝", "photograph": "📷",
    }

    cards = ""
    for h in sorted(HEIRLOOMS, key=lambda x: str(x.get("year", "9999"))):
        is_ex = is_example_entry(h)
        ex_note = '<span class="badge-tradition">Example placeholder</span>' if is_ex else ""
        origin = h.get("origin", "")
        if h.get("originId"):
            origin = person_link(h["originId"])
        photo_block = ""
        if h.get("photo"):
            photo_block = f'<div class="heirloom-photo"><img src="/img/heirlooms/{h["photo"]}" alt="{h["name"]}" onerror="this.parentElement.classList.add(\'photo-missing\');"></div>'

        recipe_block = ""
        if h.get("type") == "recipe" and h.get("recipe"):
            recipe_block = f'<div class="recipe-body">{md_to_paragraphs(h["recipe"])}</div>'

        icon = type_icons.get(h.get("type", ""), "❦")
        cards += f"""<article class="heirloom-card heirloom-{h.get("type", "object")}">
          <div class="heirloom-icon">{icon}</div>
          <div class="heirloom-body">
            {ex_note}
            <p class="dates">{h.get("year", "")} · {h.get("type", "object").upper()}</p>
            <h2>{h.get("name", "Untitled")}</h2>
            <p class="muted">From: {origin}{f' · Now with: {h["currentOwner"]}' if h.get("currentOwner") else ''}</p>
            {photo_block}
            <p>{md_to_html(h.get("description", ""))}</p>
            {recipe_block}
          </div>
        </article>"""

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Things You Can Touch</p>
    <h1>Heirlooms &amp; Recipes</h1>
    <p class="lede">The pound cake recipe, the family Bible with names in the flyleaf, the medal in the bottom drawer, the saying everyone repeats. The objects and patterns that travel through generations.</p>
  </div>
</section>

<section>
  <div class="shell">
    {empty_state_msg("Heirlooms and recipes", "Heirloom for the family archive") if not real else ""}
    {f'<p class="muted center">Currently {len(real)} real heirlooms and {len(examples)} placeholder example. To add one, edit <code>data/heirlooms.json</code>.</p>' if cards else ""}
    <div class="heirloom-stack">{cards}</div>
  </div>
</section>"""

    html = head("Heirlooms &amp; Recipes") + header(active="heirlooms") + body + footer()
    write(PUBLIC / "heirlooms.html", html)


def render_submit():
    """The contributor-facing submission page (3-mode form posting to Flask /submit)."""
    # Build a person-id select to make tagging easy
    person_options = "".join(
        f'<option value="{pid}">{p["name"]} ({p.get("lifespan","")})</option>'
        for pid, p in sorted(PEOPLE.items(), key=lambda kv: kv[1]["name"])
    )

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">Help Fill the Record</p>
    <h1>Contribute to the Family Archive</h1>
    <p class="lede">A photograph from the shoebox, a story you remember being told, a recipe in your mother's handwriting, a correction to something we got wrong — every contribution makes the record fuller and truer.</p>
  </div>
</section>

<section>
  <div class="shell narrow">

    <div class="submit-tabs" role="tablist">
      <button class="submit-tab active" data-form="form-photo"  role="tab">Add a photo or document</button>
      <button class="submit-tab"        data-form="form-story"  role="tab">Add a story or correction</button>
      <button class="submit-tab"        data-form="form-person" role="tab">Add a person</button>
    </div>

    <p class="muted" style="margin-bottom:1.4rem;">All submissions go to a moderation queue and will be incorporated into the site after review.</p>

    <!-- ============= PHOTO ============= -->
    <form id="form-photo" class="submit-form active" action="/submit" method="post" enctype="multipart/form-data">
      <input type="hidden" name="kind" value="photo">
      <h3>Add a photo or document</h3>

      <label>Image file <span class="req">*</span>
        <input type="file" name="photo_file" accept="image/*" required>
        <small>JPEG, PNG, HEIC, TIFF, etc. — up to {12} MB.</small>
      </label>

      <label>Caption <span class="req">*</span>
        <textarea name="caption" rows="3" required placeholder="Lonnie & Ruth on their wedding day, July 1948"></textarea>
      </label>

      <div class="form-row">
        <label>Year (or full date)
          <input type="text" name="year" placeholder="1948 or 1948-07-17">
        </label>
        <label>Place
          <input type="text" name="place" placeholder="Greensboro, NC">
        </label>
      </div>

      <label>Who appears in this image? (hold ⌘ / Ctrl to multi-select)
        <select name="people" multiple size="6">
          {person_options}
        </select>
      </label>

      <label>Source / where this came from
        <input type="text" name="source" placeholder="Family album, courthouse archive, Find a Grave, etc.">
      </label>

      {{submitter_block}}

      <button type="submit" class="cta-btn">Submit photo</button>
    </form>

    <!-- ============= STORY / CORRECTION ============= -->
    <form id="form-story" class="submit-form" action="/submit" method="post">
      <input type="hidden" name="kind" value="story">
      <h3>Add a story or correction</h3>

      <label>Type
        <select name="story_type">
          <option value="story">Story / oral history</option>
          <option value="correction">Correction to existing content</option>
          <option value="addition">New fact, source, or detail</option>
        </select>
      </label>

      <label>Title or short description <span class="req">*</span>
        <input type="text" name="title" required placeholder="Ruth's pound cake / Correction to Lonnie's birthplace / etc.">
      </label>

      <div class="form-row">
        <label>Year of the events
          <input type="text" name="year" placeholder="1955">
        </label>
        <label>Place
          <input type="text" name="place" placeholder="High Point, NC">
        </label>
      </div>

      <label>Who is this about? (multi-select)
        <select name="people" multiple size="6">
          {person_options}
        </select>
      </label>

      <label>Who told you this? Or, who is the source?
        <input type="text" name="teller" placeholder="My mother / Phil's daughter / family album / etc.">
      </label>

      <label>The story or correction itself <span class="req">*</span>
        <textarea name="body" rows="10" required placeholder="Tell it as you remember it. Markdown supported (**bold**, *italic*, paragraph breaks)."></textarea>
      </label>

      {{submitter_block}}

      <button type="submit" class="cta-btn">Submit story</button>
    </form>

    <!-- ============= PERSON ============= -->
    <form id="form-person" class="submit-form" action="/submit" method="post">
      <input type="hidden" name="kind" value="person">
      <h3>Add a person to the tree</h3>

      <p class="muted">Use this when you've identified a new ancestor or relative who should appear in the record. Required fields are marked.</p>

      <label>Full name <span class="req">*</span>
        <input type="text" name="name" required placeholder="William Henry Clay Quesenberry">
      </label>

      <div class="form-row">
        <label>Branch
          <select name="branch">
            <option value="">— select —</option>
            <option value="quesenberry">Quesenberry</option>
            <option value="harvey">Harvey</option>
            <option value="carmichael">Carmichael</option>
          </select>
        </label>
        <label>Generation back from Lonnie/Ruth
          <input type="number" name="generation" min="1" max="15" placeholder="3">
        </label>
      </div>

      <div class="form-row">
        <label>Birth date
          <input type="text" name="birth" placeholder="10 January 1842">
        </label>
        <label>Birthplace
          <input type="text" name="birthPlace" placeholder="Indian Valley, Floyd County, Virginia">
        </label>
      </div>

      <div class="form-row">
        <label>Death date
          <input type="text" name="death" placeholder="6 February 1898">
        </label>
        <label>Death place
          <input type="text" name="deathPlace" placeholder="Glendale, Arizona Territory">
        </label>
      </div>

      <label>Burial place
        <input type="text" name="burial" placeholder="Cemetery, town, county, state">
      </label>

      <label>Father (if known and in our tree)
        <select name="father">
          <option value="">— unknown / not yet in tree —</option>
          {person_options}
        </select>
      </label>

      <label>Mother (if known and in our tree)
        <select name="mother">
          <option value="">— unknown / not yet in tree —</option>
          {person_options}
        </select>
      </label>

      <label>Spouse (if known and in our tree)
        <select name="spouse">
          <option value="">— unknown / not yet in tree —</option>
          {person_options}
        </select>
      </label>

      <label>Brief epitaph (1–2 sentences capturing who they were)
        <textarea name="epitaph" rows="2"></textarea>
      </label>

      <label>Sources / how you know
        <textarea name="sources" rows="3" placeholder="Find a Grave URL, census record, family Bible, obituary text, etc."></textarea>
      </label>

      {{submitter_block}}

      <button type="submit" class="cta-btn">Submit person</button>
    </form>

  </div>
</section>

<script>
  document.querySelectorAll(".submit-tab").forEach(function(btn) {{
    btn.addEventListener("click", function() {{
      document.querySelectorAll(".submit-tab").forEach(function(b) {{ b.classList.toggle("active", b === btn); }});
      document.querySelectorAll(".submit-form").forEach(function(f) {{ f.classList.toggle("active", f.id === btn.dataset.form); }});
    }});
  }});
</script>"""

    submitter_block = """<fieldset class="submitter">
        <legend>About you (optional, but helps us credit you)</legend>
        <div class="form-row">
          <label>Your name
            <input type="text" name="submitter_name" placeholder="e.g. Mike Melazzo">
          </label>
          <label>Your email
            <input type="email" name="submitter_email" placeholder="so we can ask follow-ups">
          </label>
        </div>
      </fieldset>"""
    body = body.replace("{submitter_block}", submitter_block)

    html = head("Contribute") + header(active="submit") + body + footer()
    write(PUBLIC / "submit.html", html)


def render_open_questions():
    """The Open Questions page — the honest list of gaps inviting research."""
    questions = _load_optional("open-questions.json", "questions", [])

    # Group by status
    open_q   = [q for q in questions if q.get("status", "open") == "open"]
    in_prog  = [q for q in questions if q.get("status") == "in_progress"]
    closed   = [q for q in questions if q.get("status") == "closed"]

    def render_q(q, ix):
        people_links = " · ".join(person_link(pid) for pid in q.get("relatedPeople", []))
        leads = ""
        if q.get("leads"):
            leads = "<p><strong>Most likely leads:</strong></p><ul>" + "".join(f"<li>{md_to_html(l)}</li>" for l in q["leads"]) + "</ul>"
        priority = q.get("priority", "medium")
        return f"""<article class="question-card priority-{priority}" id="q-{q.get('id', ix)}">
          <header>
            <p class="dates">Question · Priority {priority.upper()}{f' · related to {q.get("branch","").title()} line' if q.get("branch") else ""}</p>
            <h2>{q.get("question", "")}</h2>
          </header>
          <p>{md_to_html(q.get("context", ""))}</p>
          {leads}
          {f'<p class="muted">Related: {people_links}</p>' if people_links else ""}
          <p class="muted submission-cta-inline">Have an answer or a lead? <a href="mailto:mike@cgcocktails.com?subject=Re: {q.get('question','')[:60]}">Send it →</a></p>
        </article>"""

    open_html   = "".join(render_q(q, i) for i, q in enumerate(open_q))
    inprog_html = "".join(render_q(q, i) for i, q in enumerate(in_prog))
    closed_html = "".join(render_q(q, i) for i, q in enumerate(closed))

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">The Honest Gaps</p>
    <h1>Open Questions</h1>
    <p class="lede">Every family record has gaps. These are ours — the questions that, when answered, will make this archive truer and fuller.</p>
  </div>
</section>

<section>
  <div class="shell narrow">

    {f'<h2>Open ({len(open_q)})</h2>{open_html}' if open_q else ''}
    {f'<h2>In progress ({len(in_prog)})</h2>{inprog_html}' if in_prog else ''}
    {f'<h2>Recently closed ({len(closed)})</h2>{closed_html}' if closed else ''}

    {empty_state_msg("Open research questions", "Lead for an open question") if not questions else ''}

  </div>
</section>"""
    html = head("Open Questions") + header(active="open-questions") + body + footer()
    write(PUBLIC / "open-questions.html", html)


def render_events_json():
    """Emit /events.json for the 'On This Day' homepage widget.
    Walks people for births/deaths/marriages and photos/stories for date-keyed events.
    Output shape: { "MM-DD": [ {year, type, summary, link} ] }
    """
    out = {}
    def add(month, day, year, kind, summary, link):
        key = f"{int(month):02d}-{int(day):02d}"
        out.setdefault(key, []).append({
            "year": int(year), "type": kind, "summary": summary, "link": link,
        })

    def parse_md_y(date_str):
        """Try to pull (month_int, day_int, year_int) from a free-form date."""
        if not date_str:
            return None
        months = {m.lower(): i for i, m in enumerate(
            ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"])}
        # pattern: "17 July 1948" or "July 17 1948" or "17 July, 1948"
        m1 = re.match(r"\s*(\d{1,2})\s+(\w+)\s+(\d{4})", date_str)
        m2 = re.match(r"\s*(\w+)\s+(\d{1,2}),?\s+(\d{4})", date_str)
        if m1:
            d, mn, yr = int(m1.group(1)), m1.group(2).lower(), int(m1.group(3))
            if mn in months: return (months[mn], d, yr)
        if m2:
            mn, d, yr = m2.group(1).lower(), int(m2.group(2)), int(m2.group(3))
            if mn in months: return (months[mn], d, yr)
        return None

    for p in PEOPLE.values():
        link = f"/people/{p['id']}.html"
        for date_field, kind, label in [
            ("birth", "birth", "Born"),
            ("death", "death", "Died"),
            ("marriedDate", "marriage", "Married"),
        ]:
            d = parse_md_y(p.get(date_field, ""))
            if d:
                mn, dy, yr = d
                summary = f"{label}: {p['name']}"
                add(mn, dy, yr, kind, summary, link)

    write(PUBLIC / "events.json", json.dumps(out, indent=2))


def main():
    print("Building Quesenberry & Harvey site...")
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    BRANCH_DIR.mkdir(parents=True, exist_ok=True)

    for p in PEOPLE.values():
        render_person_page(p)
    for branch_key in BRANCH_DEFS:
        render_branch_page(branch_key)

    render_home()
    render_tree_json()
    render_tree()
    render_timeline()
    render_military()
    render_sources()
    render_photographs()
    render_stories()
    render_places()
    render_heirlooms()
    render_open_questions()
    render_submit()
    render_events_json()

    print("Done.")


if __name__ == "__main__":
    main()
