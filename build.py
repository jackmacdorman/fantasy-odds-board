#!/usr/bin/env python3
"""Bake the ESPN leagues and the settings lock into index.html.

    python3 build.py              # rebuild index.html from what is on disk
    python3 build.py --fetch      # refresh leagues.json from ESPN first
    python3 build.py --push       # rebuild, commit and publish
    python3 build.py --fetch --push

The lock
--------
The board is public on purpose -- anyone can read the odds and see how they were
priced -- so unlike the Fantasy Rankings site there is no page content left to
hide. The same primitives do a narrower job here: PBKDF2-HMAC-SHA256 over a random
salt derives a key, and AES-GCM encrypts a short sentinel. Decrypting it is the
proof you hold the passphrase, and GCM's authentication tag is what makes that a
real check rather than a comparison against a string shipped in the page.

Be clear about what that buys. It stops a leaguemate nudging the vig slider and
arguing from a board nobody set. It cannot stop someone editing their own copy of
a public page in devtools -- nothing served statically can. The published board is
guarded by the thing that actually writes it: a push to this repo.

Set SITE_PASSPHRASE in the gitignored .env to lock the settings. Leave it unset
and the page builds with the settings open and says so on its face, which is the
right state until a passphrase exists.
"""

import argparse
import base64
import getpass
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "app.template.html"
OUT = HERE / "index.html"
LEAGUES_JSON = HERE / "leagues.json"
RATINGS_JSON = HERE / "ratings.json"

# The ciphertext is public, so it is exposed to offline guessing. Iterations are
# set high enough that each guess costs the attacker real time. Same figure as the
# Fantasy Rankings build, so the two sites are the same strength.
ITERATIONS = 600_000
MIN_LEN = 12

SENTINEL = b'{"unlock":"fantasy-futures","v":1}'

TOO_SHORT = (
    f"Use at least {MIN_LEN} characters. Anyone can download the ciphertext and guess at "
    "it offline, so length is the only thing protecting it. A few unrelated words works."
)


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def read_passphrase(interactive: bool) -> str | None:
    """SITE_PASSPHRASE from .env if set, so builds can run unattended.

    Whatever is in .env *becomes* the password on the next build -- the sentinel is
    re-encrypted from scratch every time -- so a typo there silently changes it.
    Returns None when no passphrase exists, which builds an open page on purpose.
    """
    stored = os.environ.get("SITE_PASSPHRASE", "").strip()
    if stored:
        if len(stored) < MIN_LEN:
            sys.exit(f"SITE_PASSPHRASE is too short. {TOO_SHORT}")
        print("Locking settings with SITE_PASSPHRASE from .env.")
        return stored

    if not interactive:
        return None

    pw = getpass.getpass("Passphrase (blank to leave settings open): ")
    if not pw:
        return None
    if len(pw) < MIN_LEN:
        sys.exit(f"Too short — {TOO_SHORT}")
    if pw != getpass.getpass("Again: "):
        sys.exit("Those don't match.")
    return pw


def make_lock(passphrase: str | None) -> dict | None:
    if not passphrase:
        return None
    salt, iv = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, ITERATIONS, 32)
    return {
        "salt": b64(salt),
        "iv": b64(iv),
        "ct": b64(AESGCM(key).encrypt(iv, SENTINEL, None)),
        "iter": ITERATIONS,
    }


def inject(template: str, marker: str, value) -> str:
    """Replace `/*__MARKER__*/ <default>` with a JSON literal.

    The default stays in the template so app.template.html is valid JavaScript and
    can be opened straight from disk while working on it.
    """
    needle = f"/*__{marker}__*/"
    i = template.index(needle)
    j = template.index(";", i)
    return template[:i] + json.dumps(value, separators=(",", ":")) + template[j:]


def build() -> str:
    if not LEAGUES_JSON.exists():
        sys.exit("No leagues.json — run: python3 build.py --fetch")

    leagues = json.loads(LEAGUES_JSON.read_text())
    ratings = json.loads(RATINGS_JSON.read_text()) if RATINGS_JSON.exists() else {}
    lock = make_lock(read_passphrase(interactive=sys.stdin.isatty()))

    page = TEMPLATE.read_text()
    page = inject(page, "LEAGUES", leagues)
    page = inject(page, "RATINGS", ratings)
    page = inject(page, "LOCK", lock)
    page = inject(page, "BUILT", leagues.get("fetched", date.today().isoformat()))

    OUT.write_text(page)

    teams = sum(lg["size"] for lg in leagues["leagues"])
    state = "settings LOCKED" if lock else "settings OPEN (no passphrase set)"
    print(f"Wrote {OUT.name} ({len(page)/1024:.0f} KB) — "
          f"{len(leagues['leagues'])} leagues, {teams} teams, {state}.")
    return page


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=HERE, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="refresh leagues.json from ESPN first")
    ap.add_argument("--push", action="store_true", help="commit and publish after building")
    args = ap.parse_args()

    load_dotenv(HERE / ".env")

    if args.fetch:
        subprocess.run([sys.executable, str(HERE / "espn_leagues.py")], check=True)

    build()

    if args.push:
        # index.html is generated, so it is the one file that always has something to
        # say; leagues.json only moves when --fetch ran.
        git("add", "-A")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=HERE,
                                capture_output=True, text=True).stdout.strip()
        if not status:
            print("Nothing changed — not pushing.")
            return
        git("commit", "-q", "-m", f"Rebuild board ({date.today().isoformat()})")
        git("push", "-q", "origin", "main")
        print("Pushed. GitHub Pages usually serves it within a minute.")


if __name__ == "__main__":
    main()
