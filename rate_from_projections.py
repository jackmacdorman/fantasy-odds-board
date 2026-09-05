#!/usr/bin/env python3
"""Derive preseason power ratings from ESPN's own roster projections.

    python3 rate_from_projections.py 1818479777           # show the table
    python3 rate_from_projections.py 1818479777 --write   # write into board.json

Why this rather than typed-in opinions
--------------------------------------
Before week 1 there is no PPG, so the board's From-points mode has nothing to work
on and every team rates 50. Rosters exist, though, and ESPN publishes a season
projection for every player -- in *this* league's scoring, since the projection is
fetched through the league. Summing a team's best legal starting lineup turns that
into a defensible preseason strength number that anyone can re-derive.

Starters, not the whole roster. A 16-man roster includes six bench spots, and
counting them rates hoarding rather than the lineup that actually scores each week.
Dedicated slots are filled with the best player at the position and the flex takes
the best of what is left, which is optimal here because the flex accepts a superset
of the dedicated positions.

The z-score step is the one the board already documents for PPG:

    rating = 50 + 15 x (strength - league mean) / stdev

Raw projections are far too compressed to use directly -- the best and worst rosters
in a ten-team league differ by maybe 15%, and at k=3 that is nearly a flat board.
Re-centring spreads a normal league across roughly 20-80, which is the range the
spread dial is built for.

These are a starting point, not a verdict. ESPN's projections know nothing about who
drafted well for a specific matchup, and they are wrong about somebody every year.
Adjust by hand in the page afterwards.
"""

import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from espn_api.football import League

HERE = Path(__file__).resolve().parent
BOARD = HERE / "board.json"

FLEX = {"RB/WR/TE": {"RB", "WR", "TE"}, "WR/TE": {"WR", "TE"}, "RB/WR": {"RB", "WR"},
        "OP": {"QB", "RB", "WR", "TE"}}


def best_lineup(roster, slots):
    """Sum the highest-projecting legal starting lineup."""
    pool = sorted(
        ((float(getattr(p, "projected_total_points", 0) or 0), p.position, p.name)
         for p in roster),
        reverse=True,
    )
    used, total, chosen = set(), 0.0, []

    def take(match, n):
        nonlocal total
        for i, (pts, pos, name) in enumerate(pool):
            if n <= 0:
                break
            if i in used or not match(pos):
                continue
            used.add(i); total += pts; chosen.append((name, pos, pts)); n -= 1

    # Dedicated slots first; the flex then takes the best of whatever is left.
    for pos, count in slots.items():
        if pos in ("BE", "IR") or pos in FLEX or not count:
            continue
        take(lambda p, want=pos: p == want, count)
    for pos, count in slots.items():
        if pos in FLEX and count:
            take(lambda p, ok=FLEX[pos]: p in ok, count)

    return total, chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("league_id")
    ap.add_argument("--write", action="store_true", help="write the ratings into board.json")
    args = ap.parse_args()

    load_dotenv(HERE / ".env")
    lg = League(league_id=int(args.league_id), year=int(os.environ["ESPN_SEASON_YEAR"]),
                espn_s2=os.environ["ESPN_S2"], swid=os.environ["ESPN_SWID"])

    slots = {k: v for k, v in lg.settings.position_slot_counts.items() if v}
    if not lg.draft:
        sys.exit(f"{lg.settings.name} has not drafted yet — there are no rosters to rate.")

    rows = []
    for t in lg.teams:
        strength, _ = best_lineup(t.roster, slots)
        rows.append({"id": str(t.team_id), "name": t.team_name.strip(), "strength": strength})

    vals = [r["strength"] for r in rows]
    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    for r in rows:
        r["rating"] = round(50 + 15 * (r["strength"] - mean) / sd, 1) if sd else 50.0

    rows.sort(key=lambda r: -r["rating"])
    print(f"{lg.settings.name} — {len(rows)} teams, "
          f"lineup {', '.join(f'{v}x{k}' for k, v in slots.items() if k not in ('BE','IR'))}")
    print(f"projected starting lineup: mean {mean:.0f}, stdev {sd:.0f} "
          f"({min(vals):.0f}–{max(vals):.0f}, a {max(vals)/min(vals):.2f}x spread)\n")
    print(f"{'':2} {'TEAM':<26} {'PROJ':>7}  {'RATING':>6}")
    for i, r in enumerate(rows, 1):
        print(f"{i:>2} {r['name'][:26]:<26} {r['strength']:>7.0f}  {r['rating']:>6.1f}")

    if not args.write:
        print("\n(nothing written — pass --write to put these in board.json)")
        return

    board = json.loads(BOARD.read_text()) if BOARD.exists() else {"version": 1, "leagues": {}}
    entry = board.setdefault("leagues", {}).setdefault(str(lg.league_id), {})
    entry.setdefault("settings", {})
    # Ratings only. Anything already set for this league stays as it is.
    by_id = {r["id"]: r for r in rows}
    existing = {t.get("id"): t for t in entry.get("teams", [])}
    entry["teams"] = [
        {"id": r["id"], "name": existing.get(r["id"], {}).get("name", r["name"]),
         "rating": r["rating"]}
        for r in sorted(rows, key=lambda x: -x["rating"])
    ]
    board["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    BOARD.write_text(json.dumps(board, indent=2) + "\n")
    print(f"\nWrote {len(rows)} ratings into {BOARD.name} (updated {board['updated']}).")


if __name__ == "__main__":
    main()
