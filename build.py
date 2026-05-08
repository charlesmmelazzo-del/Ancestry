#!/usr/bin/env python3
"""
Build script for the Quesenberry & Harvey Family History static site.

Reads data/people.json and renders HTML pages into public/.
Run:  python3 build.py
"""

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

with open(DATA) as f:
    DATABASE = json.load(f)

PEOPLE = DATABASE["people"]
SITE = DATABASE["site"]


# ---- helpers ----------------------------------------------------------------

def md_to_html(text: str) -> str:
    """Tiny markdown-ish: *italic* and **bold**, plus paragraph wrapping."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def person_link(person_id):
    if person_id in PEOPLE:
        p = PEOPLE[person_id]
        return f'<a href="/people/{person_id}.html">{p["name"]}</a>'
    return person_id


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
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400;1,700&family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&family=Cormorant+SC:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/style.css">
</head>
<body>
"""


def header(active=""):
    def cls(name):
        return ' class="active"' if name == active else ""
    return f"""<header class="site-header">
  <div class="shell">
    <h1 class="site-title"><a href="/">{SITE['title']}</a></h1>
    <nav class="site-nav" aria-label="Main">
      <a href="/"{cls('home')}>Home</a>
      <a href="/branches/quesenberry.html"{cls('quesenberry')}>Quesenberry</a>
      <a href="/branches/harvey.html"{cls('harvey')}>Harvey</a>
      <a href="/branches/carmichael.html"{cls('carmichael')}>Carmichael</a>
      <a href="/tree.html"{cls('tree')}>Family Tree</a>
      <a href="/military.html"{cls('military')}>Military</a>
      <a href="/timeline.html"{cls('timeline')}>Timeline</a>
      <a href="/sources.html"{cls('sources')}>Sources</a>
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


# ---- person page ------------------------------------------------------------

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

    # narrative
    paragraphs = p.get("narrative", [])
    body_html = ""
    for i, para in enumerate(paragraphs):
        cls = ' class="dropcap"' if i == 0 else ""
        body_html += f"<p{cls}>{md_to_html(para)}</p>\n"

    military_badge = ""
    if "military" in p:
        military_badge = f'<p><span class="badge-military">⚔ {p["military"]}</span></p>'

    # Verification badge
    verification_badge = ""
    v = p.get("verified", "")
    if v == "documented":
        verification_badge = '<p><span class="badge-verified">✓ Documented from public records</span></p>'
    elif v == "partial":
        verification_badge = '<p><span class="badge-partial">◐ Partial — name documented, other facts await further research</span></p>'
    elif v == "tradition":
        verification_badge = '<p><span class="badge-tradition">○ Family tradition — not yet confirmed in primary records</span></p>'

    html = head(name)
    html += header(active=p.get("branch", ""))
    html += f"""
<section class="person-header">
  <div class="shell">
    <p class="section-eyebrow">{p.get('branch', '').title()} Line — Generation {p.get('generation', '?')}</p>
    <h1>{name}</h1>
    <p class="lifespan">{lifespan}</p>
    {f'<p class="epitaph">{md_to_html(epitaph)}</p>' if epitaph else ''}
  </div>
</section>

<section class="person-body">
  <div class="shell">
    <div class="person-grid">
      <article class="narrow">
        {verification_badge}
        {military_badge}
        {body_html}
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
    "carmichael": {
        "title": "The Carmichael Line",
        "subtitle": "Highland Scotland → Ulster → the Cape Fear of North Carolina",
        "intro": (
            "Carmichael is one of the great Scottish names — from a Lanarkshire parish, a sept of Clan Douglas, of Clan "
            "MacDougall, and of the Stewarts of Appin. The Carmichael migration to North Carolina came in two great waves "
            "in the 1770s. Geneva Carmichael, Ruth Garland Harvey's mother, almost certainly descends from this Highland "
            "migration — most likely from Archibald Carmichael, who left Larne Harbor on the ship Jupiter of Larne on his "
            "twenty-first birthday in September 1775, bound for Wilmington."
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
<section class="hero">
  <div class="shell">
    <p class="kicker">{SITE['subtitle']}</p>
    <h1>{SITE['title']}</h1>
    <div class="hero-divider"></div>
    <p class="lede">{SITE['tagline']}</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    <p class="dropcap">{md_to_html(SITE['intro'])}</p>
    <p>This site collects what is presently known of the ancestors of <a href="/people/lonnie-quesenberry.html">Lonnie Olin Quesenberry</a> (1920–2002) and <a href="/people/ruth-harvey.html">Ruth Garland Harvey Quesenberry</a> (1925–2016) — the maternal grandparents of the family for whom this record was made. From them the trail runs back through the Quesenberry, Slusher (Schlosser), Hylton, Harvey, and Carmichael families to colonial Virginia, the Palatinate Germany of the 1700s, the Highlands of Scotland, and Kent, England in the reign of King James I.</p>
    <p>Browse by family line, by generation, or by the names that recur — Eva, Archibald, Aaron, Thomas, John — across the centuries.</p>
  </div>
</section>

<section>
  <div class="shell">
    <h2>Where to Begin</h2>
    <div class="card-grid">
      <article class="card">
        <h3>The three family lines</h3>
        <p>Each branch tells its own story. <a href="/branches/quesenberry.html">Quesenberry</a> from Kent in 1624. <a href="/branches/harvey.html">Harvey</a> from the colonial English diaspora. <a href="/branches/carmichael.html">Carmichael</a> from the Scottish Highlands of 1775.</p>
      </article>
      <article class="card">
        <h3>The full family tree</h3>
        <p>An at-a-glance view of how the lines connect, generation by generation. <a href="/tree.html">View the tree →</a></p>
      </article>
      <article class="card">
        <h3>Military service</h3>
        <p>From the American Revolution to the Civil War to (likely) the Second World War. <a href="/military.html">See the soldiers →</a></p>
      </article>
      <article class="card">
        <h3>Timeline</h3>
        <p>Four centuries of family events set against the larger story of America. <a href="/timeline.html">View the timeline →</a></p>
      </article>
    </div>
  </div>
</section>

<section>
  <div class="shell">
    <h2>Featured Ancestors</h2>
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


# ---- tree page --------------------------------------------------------------

def render_tree():
    """Render an SVG ancestor tree centered on Lonnie + Ruth's children's generation
    (i.e. their parents) going back."""

    svg = """<svg class="tree-svg" viewBox="0 0 1200 760" xmlns="http://www.w3.org/2000/svg">
  <style>
    .node-box { fill: #efe2c4; stroke: #7a4a1f; stroke-width: 1.2; }
    .node-name { font-family: 'Playfair Display', Georgia, serif; font-size: 14px; font-style: italic; fill: #2b1d10; }
    .node-dates { font-family: 'Cormorant SC', Georgia, serif; font-size: 11px; letter-spacing: 0.06em; fill: #7a4a1f; }
    .branch-line { stroke: #b89b6f; stroke-width: 1.2; fill: none; }
    .gen-label { font-family: 'Cormorant SC', Georgia, serif; font-size: 11px; letter-spacing: 0.18em; fill: #7a4a1f; text-transform: uppercase; }
  </style>

  <!-- generation labels -->
  <text x="20" y="60" class="gen-label">Gen 1 (Grandparents)</text>
  <text x="20" y="200" class="gen-label">Gen 2 (Great-Grandparents)</text>
  <text x="20" y="340" class="gen-label">Gen 3</text>
  <text x="20" y="480" class="gen-label">Gens 4–6</text>
  <text x="20" y="620" class="gen-label">Gen 9 (Immigrants)</text>

  <!-- Generation 1: Lonnie + Ruth -->
  <a href="/people/lonnie-quesenberry.html"><rect x="320" y="80" width="240" height="60" class="node-box"/><text x="440" y="105" text-anchor="middle" class="node-name">Lonnie Olin Quesenberry</text><text x="440" y="125" text-anchor="middle" class="node-dates">1920 – 2002</text></a>
  <a href="/people/ruth-harvey.html"><rect x="640" y="80" width="240" height="60" class="node-box"/><text x="760" y="105" text-anchor="middle" class="node-name">Ruth Garland Harvey</text><text x="760" y="125" text-anchor="middle" class="node-dates">1925 – 2016</text></a>

  <!-- marriage line -->
  <line x1="560" y1="110" x2="640" y2="110" class="branch-line"/>

  <!-- Gen 2 -->
  <a href="/people/floyd-quesenberry.html"><rect x="160" y="220" width="200" height="60" class="node-box"/><text x="260" y="245" text-anchor="middle" class="node-name">Floyd H. Quesenberry</text><text x="260" y="265" text-anchor="middle" class="node-dates">fl. 1920s</text></a>
  <a href="/people/eva-quesenberry.html"><rect x="380" y="220" width="200" height="60" class="node-box"/><text x="480" y="245" text-anchor="middle" class="node-name">Eva Quesenberry</text><text x="480" y="265" text-anchor="middle" class="node-dates">fl. 1920s</text></a>
  <a href="/people/carl-harvey.html"><rect x="600" y="220" width="200" height="60" class="node-box"/><text x="700" y="245" text-anchor="middle" class="node-name">Carl Harvey</text><text x="700" y="265" text-anchor="middle" class="node-dates">fl. 1920s</text></a>
  <a href="/people/geneva-carmichael.html"><rect x="820" y="220" width="220" height="60" class="node-box"/><text x="930" y="245" text-anchor="middle" class="node-name">Geneva Carmichael Harvey</text><text x="930" y="265" text-anchor="middle" class="node-dates">fl. 1920s</text></a>

  <!-- lines from gen 1 to gen 2 -->
  <path d="M 440 140 V 180 H 260 V 220" class="branch-line"/>
  <path d="M 440 140 V 180 H 480 V 220" class="branch-line"/>
  <path d="M 760 140 V 180 H 700 V 220" class="branch-line"/>
  <path d="M 760 140 V 180 H 930 V 220" class="branch-line"/>

  <!-- Gen 3 (illustrative — Quesenberry and Carmichael lines documented further back) -->
  <a href="/people/william-henry-quesenberry.html"><rect x="80" y="360" width="240" height="60" class="node-box"/><text x="200" y="385" text-anchor="middle" class="node-name">William Henry Quesenberry</text><text x="200" y="405" text-anchor="middle" class="node-dates">1841 – 1898</text></a>
  <a href="/people/eva-jane-slusher.html"><rect x="340" y="360" width="240" height="60" class="node-box"/><text x="460" y="385" text-anchor="middle" class="node-name">Eva Jane Slusher Quesenberry</text><text x="460" y="405" text-anchor="middle" class="node-dates">1838 – 1926</text></a>

  <!-- line from Floyd up to William Henry / Eva Jane -->
  <path d="M 260 280 V 330 H 200 V 360" class="branch-line"/>
  <path d="M 260 280 V 330 H 460 V 360" class="branch-line"/>

  <!-- Gen 4–5–6 stack (Quesenberry line) -->
  <a href="/people/john-quesenberry-sr.html"><rect x="80" y="500" width="240" height="50" class="node-box"/><text x="200" y="525" text-anchor="middle" class="node-name">John Quesenberry Sr.</text><text x="200" y="545" text-anchor="middle" class="node-dates">c.1790s – 1853</text></a>
  <a href="/people/george-quesenberry.html"><rect x="80" y="555" width="240" height="50" class="node-box"/><text x="200" y="580" text-anchor="middle" class="node-name">George Quesenberry (Rev. War)</text><text x="200" y="600" text-anchor="middle" class="node-dates">1748 – 1812</text></a>
  <a href="/people/aaron-quisenberry.html"><rect x="80" y="610" width="240" height="50" class="node-box"/><text x="200" y="635" text-anchor="middle" class="node-name">Aaron Quisenberry Sr. (DAR)</text><text x="200" y="655" text-anchor="middle" class="node-dates">1725 – 1795</text></a>

  <path d="M 200 420 V 460 H 200 V 500" class="branch-line"/>

  <!-- Gen 8/9 immigrants -->
  <a href="/people/john-quisenberry-1627.html"><rect x="80" y="675" width="240" height="50" class="node-box"/><text x="200" y="700" text-anchor="middle" class="node-name">John Quisenberry (b. 1627 VA)</text><text x="200" y="720" text-anchor="middle" class="node-dates">first American-born</text></a>
  <a href="/people/thomas-questenbury.html"><rect x="340" y="675" width="240" height="50" class="node-box"/><text x="460" y="700" text-anchor="middle" class="node-name">Thomas Questenbury (immigrant)</text><text x="460" y="720" text-anchor="middle" class="node-dates">Kent → VA, 1624</text></a>

  <!-- Carmichael immigrant -->
  <a href="/people/archibald-carmichael.html"><rect x="780" y="675" width="280" height="50" class="node-box"/><text x="920" y="700" text-anchor="middle" class="node-name">Archibald Carmichael (immigrant)</text><text x="920" y="720" text-anchor="middle" class="node-dates">Scotland → NC, 1775</text></a>

  <path d="M 930 280 V 660 H 920 V 675" class="branch-line"/>
</svg>"""

    body = f"""<section class="branch-hero">
  <div class="shell">
    <p class="section-eyebrow">A Visual Map</p>
    <h1>The Family Tree</h1>
    <p class="lede">From Lonnie and Ruth's parents back to the immigrants who crossed the Atlantic — Kent in 1624, Lanarkshire in 1775, the German Palatinate in the early 1700s.</p>
  </div>
</section>

<section>
  <div class="shell">
    <div class="tree-wrapper">
      {svg}
    </div>
    <p class="muted center">Click any name to read the full profile. Some intermediate generations are not yet pictured here — see each branch page for the complete known list.</p>
  </div>
</section>

<section>
  <div class="shell narrow">
    <h2>How to read this tree</h2>
    <p>The tree is read top-to-bottom, oldest at the bottom. The grandparents' generation sits at the top. As you move down the page you move backward in time — to great-grandparents, then their parents, and so on, until you reach the Atlantic-crossing ancestors at the foot of the page.</p>
    <p>The Quesenberry line is the most fully documented, reaching back nine generations to the colonial Virginia immigrant Thomas Questenbury, who arrived in the colony in 1624. The Carmichael line is documented to Archibald Carmichael of Lanarkshire, Scotland, who landed at Wilmington in 1775. The Harvey line, on the present record, is documented only to Ruth's father Carl Harvey — but its colonial roots are almost certainly in the same Tidewater Virginia / Carolina Piedmont migration.</p>
    <p>The dotted gaps in the tree mark the places where the Floyd County, Virginia and Guilford County, North Carolina courthouse records — many of which still wait in the basement filing cabinets of those counties — could fill in the next generation of the story.</p>
  </div>
</section>"""

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

def main():
    print("Building Quesenberry & Harvey site...")
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    BRANCH_DIR.mkdir(parents=True, exist_ok=True)

    for p in PEOPLE.values():
        render_person_page(p)
    for branch_key in BRANCH_DEFS:
        render_branch_page(branch_key)

    render_home()
    render_tree()
    render_timeline()
    render_military()
    render_sources()

    print("Done.")


if __name__ == "__main__":
    main()
