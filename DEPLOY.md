# Deploying the Quesenberry & Harvey Family Site

Three options, ranked by what "easy to update" really means.

---

## Option 1 — Cloudflare Pages + GitHub  ⭐ RECOMMENDED

**Free forever. Updates in 60 seconds whenever you push.**

### One-time setup (~10 minutes total)

1. **Create a GitHub account** at https://github.com/signup if you don't have one. Free, takes 2 minutes.

2. **Install GitHub Desktop** (optional but very friendly): https://desktop.github.com — gives you a button-driven interface instead of typing git commands.

3. **Create a new repository on GitHub:**
   - Go to https://github.com/new
   - Name it something like `quesenberry-harvey-family` (this becomes part of the URL)
   - Set it to **Private** if you want only family to see the source code (the *site* itself will still be public).
   - Don't add a README — we already have one.
   - Click **Create repository**.

4. **Push this folder to GitHub:**
   - Open Terminal (Mac) or Command Prompt (Windows).
   - Navigate to this folder:
     ```bash
     cd "<path to quesenberry_harvey_genealogy folder>"
     ```
   - Run these commands (copy the URL from the page GitHub showed you in step 3):
     ```bash
     git init
     git add .
     git commit -m "Initial family history site"
     git branch -M main
     git remote add origin https://github.com/YOUR_USERNAME/quesenberry-harvey-family.git
     git push -u origin main
     ```
   - GitHub will ask you to log in. If you have GitHub Desktop installed, it handles this automatically.

5. **Connect Cloudflare Pages:**
   - Sign up at https://dash.cloudflare.com/sign-up (free, 2 min).
   - In the dashboard, click **Workers & Pages → Create → Pages → Connect to Git**.
   - Authorize Cloudflare to read your GitHub repos.
   - Select the `quesenberry-harvey-family` repo.
   - **Build settings:**
     - Framework preset: **None**
     - Build command: `python3 build.py`
     - Build output directory: `public`
   - Click **Save and Deploy**.
   - In about 90 seconds your site is live at `https://quesenberry-harvey-family.pages.dev`.

6. **(Optional) Custom domain:** In Cloudflare Pages → your project → **Custom domains → Set up a custom domain**. If you own a domain (e.g., `quesenberryfamily.com`), point it here. Free.

### Ongoing — when we add new research:

After our sessions, I'll edit `data/people.json` and rebuild. To publish:

**With GitHub Desktop:** Open the app, you'll see the changes listed, type a short summary like "Added Lonnie's WWII draft card," click **Commit to main**, then **Push origin**. Done.

**With command line:** From the project folder:
```bash
git add .
git commit -m "Added Lonnie's WWII draft card"
git push
```

Cloudflare detects the push and rebuilds the site. Live in ~60 seconds.

---

## Option 2 — GitHub Pages

Almost identical to Option 1, but the site is hosted by GitHub instead of Cloudflare. Slightly slower CDN, but everything stays in one place. Site lives at `https://YOUR_USERNAME.github.io/quesenberry-harvey-family`.

### Setup difference:
- Same steps 1–4 as above.
- **Step 5 is different — enable GitHub Pages:**
  - In your GitHub repo, go to **Settings → Pages**.
  - **Source:** Deploy from a branch.
  - **Branch:** main, folder: `/public`.
  - Click **Save**.
  - Live in ~30 seconds at `https://YOUR_USERNAME.github.io/quesenberry-harvey-family`.

⚠️ **Caveat:** GitHub Pages doesn't run Python. If you want to use the build script, switch the source to **GitHub Actions** instead — see GitHub's docs at https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site#publishing-with-a-custom-github-actions-workflow — or just commit the pre-built `public/` folder and ignore the script (works fine).

---

## Option 3 — Netlify Drop  (zero setup, zero account)

Truly plug-and-play if you don't want to deal with Git at all:

1. Go to https://app.netlify.com/drop
2. Drag the `public/` folder onto the page.
3. Site is live in 30 seconds at a randomly-generated URL like `https://random-words-12345.netlify.app`.
4. Sign up to claim the site and get a custom subdomain or domain.

**Trade-off:** You have to drag-and-drop again every time we update. Not bad if updates are rare.

---

## Option 4 — Neocities  (no Git, simple dashboard)

Old-school free hosting beloved by hobbyist sites:

1. Sign up at https://neocities.org (free).
2. Use their web dashboard to upload the contents of `public/`.
3. Site lives at `https://YOUR_NAME.neocities.org`.

**Trade-off:** Same as Netlify Drop — re-upload every time.

---

## Why I recommend Option 1

- **Free forever** — Cloudflare Pages has no usage cap that you'll ever hit for a family site.
- **Auto-deploy** — push once, the site rebuilds itself.
- **Reliable** — Cloudflare's CDN is the fastest in the world; the site loads instantly from anywhere on Earth.
- **Future-proof** — when we add photos, videos, audio recordings of family members, the same workflow handles it.
- **Version history** — GitHub keeps a permanent record of every change. If anything goes wrong, we can always roll back.

---

## When we work together again

Once the site is on GitHub:
1. You open Claude in this session folder.
2. We do a research session — I edit `data/people.json`, run `python3 build.py`, verify locally.
3. You run `git push` (or click Push in GitHub Desktop).
4. The live site updates in 60 seconds.

That's it. The "I sync changes for you" workflow is one button click on your end.
