#!/usr/bin/env python3
"""Pull team names, owners and scoring from every ESPN league the board can price.

ESPN's fantasy API needs account cookies and does not send CORS headers, so the
browser cannot call it. The data is fetched here and baked into the page at build
time instead -- the same arrangement the Fantasy Rankings board uses.

    python3 espn_leagues.py            # refresh leagues.json
    python3 espn_leagues.py --show     # refresh and print what came back
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from espn_api.football import League

HERE = Path(__file__).resolve().parent
OUT = HERE / "leagues.json"

# The same four leagues the Fantasy Rankings board carries. Ids, not names: ESPN
# league names get changed mid-season (this account has already renamed one), and
# an id survives that.
LEAGUES = {
    "62403137": "Ligma Ep",
    "1490615607": "Modern Family Fantasy",
    "1818479777": "Rollin' Deep",
    "1098609042": "XFL",
}


def owner_name(owner: dict) -> str:
    """A readable owner name.

    ESPN's displayName is often an auto-generated handle -- this account's own reads
    "ESPNFAN2950190288" -- so the real first/last name wins when it is there, and
    displayName is only the fallback.
    """
    first = (owner.get("firstName") or "").strip()
    last = (owner.get("lastName") or "").strip()
    full = f"{first} {last}".strip()
    return full or (owner.get("displayName") or "").strip() or "—"


def owners_of(team) -> str:
    names = [owner_name(o) for o in (team.owners or []) if isinstance(o, dict)]
    seen = [n for i, n in enumerate(names) if n and n not in names[:i]]
    return " & ".join(seen[:2]) if seen else "—"


def fetch_league(league_id: str, label: str, year: int) -> dict:
    league = League(
        league_id=int(league_id),
        year=year,
        espn_s2=os.environ["ESPN_S2"],
        swid=os.environ["ESPN_SWID"],
    )

    teams = []
    for t in league.teams:
        # Games played comes from the record rather than len(scores): ESPN pads the
        # schedule out to the full season, so every unplayed week is a 0 that would
        # otherwise drag a real average down.
        games = int(t.wins) + int(t.losses) + int(t.ties)
        pf = float(t.points_for or 0.0)
        teams.append({
            "id": str(t.team_id),
            "name": t.team_name.strip(),
            "owner": owners_of(t),
            "games": games,
            "pf": round(pf, 2),
            "ppg": round(pf / games, 2) if games else None,
        })

    return {
        "id": league_id,
        # ESPN's own current name, falling back to the label above if it is missing.
        "name": (getattr(league.settings, "name", "") or label).strip() or label,
        "size": len(teams),
        "week": int(getattr(league, "current_week", 0) or 0),
        "teams": teams,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="print what came back")
    args = ap.parse_args()

    load_dotenv(HERE / ".env")
    year = int(os.environ.get("ESPN_SEASON_YEAR", date.today().year))

    payload = {
        "fetched": date.today().isoformat(),
        "season": year,
        "leagues": [fetch_league(lid, label, year) for lid, label in LEAGUES.items()],
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    played = sum(t["games"] for lg in payload["leagues"] for t in lg["teams"])
    print(f"Wrote {OUT.name}: {len(payload['leagues'])} leagues, "
          f"{sum(lg['size'] for lg in payload['leagues'])} teams, season {year}.")
    if not played:
        print("No games played yet — every PPG is null, so the board rates every team "
              "equally until real scores exist.")

    if args.show:
        for lg in payload["leagues"]:
            print(f"\n{lg['name']} ({lg['id']}) — {lg['size']} teams, week {lg['week']}")
            for t in lg["teams"]:
                ppg = "—" if t["ppg"] is None else f"{t['ppg']:.1f}"
                print(f"   {t['name'][:34]:<34}  {t['owner'][:22]:<22}  PPG {ppg}")


if __name__ == "__main__":
    main()
