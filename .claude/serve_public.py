#!/usr/bin/env python3
"""Tiny static server for /public — avoids os.getcwd() in http.server CLI."""
import os, sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = "/Users/charles/Documents/Claude/Projects/quesenberry_harvey_genealogy/.claude/worktrees/vibrant-euler-c92460/public"
PORT = int(os.environ.get("PORT", "8765"))

os.chdir(ROOT)
handler = partial(SimpleHTTPRequestHandler, directory=ROOT)
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
print(f"Serving {ROOT} at http://127.0.0.1:{PORT}", flush=True)
httpd.serve_forever()
