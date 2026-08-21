"""Stamp every image reference in the web app with a content hash.

The web app asks for /static/img/banner.png and always has. When the file
behind that name changes, a browser that already has a copy has no reason to
believe it is stale, so it keeps showing the old one - through a reload, and
often through a hard reload too. That is not a browser bug; nothing in the
response told it otherwise.

This appends ?v=<hash of that file> to each reference. Change an image and its
hash changes, so the url changes, so every cache on the way - browser, proxy,
whatever PythonAnywhere puts in front - has to fetch it. Leave an image alone
and its url is unchanged, so it stays cached, which is the point.

Per file rather than one version for all of them: swapping one icon should not
force everybody to re-download the banner.

    python3 stamp_assets.py

Run it after changing anything under webapp/static/img/, and before deploying.
"""

import hashlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
WEBAPP = ROOT / "webapp"
PAGES = ["index.html", "app.html", "download.html"]

# src="/static/img/thing.png" with an optional ?v=... already on it.
REF = re.compile(r'(/static/img/([A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|webp|svg)))(\?v=[0-9a-f]+)?')


def digest(name: str) -> str | None:
    path = WEBAPP / "static" / "img" / name
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def stamp(page: Path) -> int:
    text = io.open(page, encoding="utf-8").read()
    missing, stamped = [], []

    def replace(m):
        url, name, _old = m.group(1), m.group(2), m.group(3)
        h = digest(name)
        if h is None:
            missing.append(name)
            return m.group(0)
        stamped.append(name)
        return "%s?v=%s" % (url, h)

    out = REF.sub(replace, text)
    if out != text:
        io.open(page, "w", encoding="utf-8", newline="").write(out)

    for name in sorted(set(missing)):
        print("  MISSING  %s  (referenced but not on disk)" % name)
    print("  %-14s %d references stamped, %d distinct files"
          % (page.name, len(stamped), len(set(stamped))))
    return len(missing)


def main() -> int:
    print("stamping image urls with content hashes")
    missing = 0
    for name in PAGES:
        page = WEBAPP / name
        if page.exists():
            missing += stamp(page)
    if missing:
        print()
        print("  Some references point at files that do not exist. Those are")
        print("  broken images today, cache or no cache.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
