# The Quesenberry & Harvey Family History

A Ken Burns-style documentary website tracing the ancestors of **Lonnie Olin Quesenberry** (1920–2002) and **Ruth Garland Harvey Quesenberry** (1925–2016) back through four centuries of American history — from Kent in 1624 and Lanarkshire in 1775 to the Carolina Piedmont of the present day.

## What's here

- **Three family lines** — Quesenberry (Virginia, since 1624), Harvey (Carolina Piedmont), Carmichael (Highland Scots, since 1775).
- **14 individual ancestor profiles** — written in a long-form narrative voice, with vital records and source citations.
- **A visual family tree** linking the generations.
- **A timeline** placing the family story against the spine of American history.
- **A military service page** highlighting Revolutionary War and Civil War ancestors.
- **A sources & methodology page** documenting every claim.

## How it's built

- All content lives in **`data/people.json`** — a single human-readable file. No CMS, no database.
- A small Python script (`build.py`) renders the JSON into static HTML pages in `public/`.
- The site is served by **nginx** in a 25 MB Docker container.

## Local preview

```bash
python3 build.py            # builds public/
cd public
python3 -m http.server 8000 # then open http://localhost:8000
```

## Deploy to Railway

1. Push this folder to a new GitHub repository.
2. In Railway, click **New Project → Deploy from GitHub Repo** and select it.
3. Railway will detect the `Dockerfile` and `railway.json` automatically and build & deploy the site.
4. Add a custom domain in **Settings → Networking** if desired.

That's it. No environment variables required.

## Editing the family record

The single source of truth is `data/people.json`. To add an ancestor:

1. Copy an existing person record in the JSON.
2. Set a unique `id` (lowercase, hyphenated).
3. Fill in `name`, `lifespan`, `birth`, `death`, `branch`, `generation`, `epitaph`, and `narrative` (an array of paragraphs).
4. Link to parents via `father` / `mother` and to a spouse via `spouse`. Add the new id to the parents' `children` array.
5. Run `python3 build.py`.
6. Commit and push — Railway will redeploy automatically.

The Python script supports a tiny markdown-ish syntax inside narrative paragraphs:

- `*italic*` → *italic*
- `**bold**` → **bold**

## What needs further research

The site marks itself honestly where the record is incomplete. The most important next steps:

- **Connect Floyd H. Quesenberry to the documented Quesenberry tree** (most likely a descendant of William Henry Quesenberry of Indian Valley, Floyd County, VA).
- **Eva Quesenberry's maiden name** — currently unknown.
- **Carl Harvey's parents** — Guilford County records, unsearched.
- **Geneva Carmichael's link to Archibald Carmichael's documented descendants** — almost certainly direct, but unverified.
- **Lonnie Quesenberry's WWII military record** — request from the National Personnel Records Center, St. Louis.
- **The full 1862 Quesenberry Confederate muster roll** — held at the Virginia Museum of History & Culture, Richmond.

See `/sources.html` on the live site for the full list of sources used and questions outstanding.

## File layout

```
/
├── data/
│   └── people.json          ← all content lives here
├── public/                   ← generated HTML (rebuild with build.py)
│   ├── index.html
│   ├── tree.html, timeline.html, military.html, sources.html
│   ├── branches/             ← per-line overview pages
│   ├── people/               ← per-ancestor profile pages
│   └── css/style.css
├── build.py                  ← static-site generator
├── Dockerfile                ← multi-stage build (Python → nginx)
├── nginx.conf                ← server config
├── railway.json              ← Railway deployment config
└── README.md
```

## Credit

Compiled from public sources including Find a Grave, FamilySearch, WikiTree, Geni, the Virginia Museum of History & Culture, the Floyd County Historical Society, and the obituaries published by Cumby Family Funeral Service of High Point, NC.

Built for the descendants of Lonnie & Ruth Quesenberry — May 2026.
