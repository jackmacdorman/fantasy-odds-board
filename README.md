# Fantasy Futures

A commissioner's tool that turns fantasy power ratings into a two-sided betting
market — odds to win the league, and odds to finish last — across all four ESPN
leagues.

**Live:** https://jackmacdorman.github.io/fantasy-odds-board/

## Running it

```bash
python3 build.py --fetch --push     # pull ESPN, rebuild, publish
python3 build.py                    # rebuild from what's on disk
python3 espn_leagues.py --show      # just look at what ESPN returns
```

`index.html` is **generated** — edit `app.template.html` and rebuild. The template
is valid HTML and JavaScript on its own, so it still opens straight from disk while
you work on it; the baked-in data sits behind `/*__MARKER__*/` comments that
`build.py` replaces.

## ESPN

`espn_leagues.py` pulls team names, owners and points from all four leagues into
`leagues.json`, which `build.py` bakes into the page. It has to work that way:
ESPN's fantasy API needs account cookies and sends no CORS headers, so a browser
can't call it directly. Credentials live in a gitignored `.env` — the same
account-level `ESPN_S2` / `ESPN_SWID` cookies the Fantasy Rankings project uses.

| League | ID | Teams |
|---|---|---|
| Ligma Ep | 62403137 | 12 |
| Modern Family Fantasy | 1490615607 | 10 |
| Rollin' Deep | 1818479777 | 10 |
| XFL | 1098609042 | 12 |

**Games played comes from the record, not from `len(scores)`** — ESPN pads the
schedule to the full season, so every unplayed week is a `0` that would drag a real
average down. Preseason, every PPG is therefore `null` rather than `0.0`, and the
board says "no games played yet" instead of rating everyone off fake zeros.

Owner names prefer ESPN's first/last name over `displayName`, which is often an
auto-generated handle (this account's own reads `ESPNFAN2950190288`).

Manual ratings live in `ratings.json`, keyed by league id then **ESPN team id** —
ids, not names, so a mid-season team rename doesn't orphan a rating. Anything
missing defaults to 50.

## The settings lock

The board is public on purpose: anyone can read the odds and see exactly how they
were priced. Only someone with the passphrase can move the sliders. Locked, the
rows render as text rather than as greyed-out inputs, and the League selector,
the American/Decimal toggle and both copy buttons stay live.

Set it, then rebuild:

```bash
python3 build.py --push
```

**What the crypto does.** PBKDF2-HMAC-SHA256, 600,000 iterations over a random
16-byte salt, then AES-GCM — the same primitives and the same iteration count as
the Fantasy Rankings site. There, they hide the entire page. Here the page is meant
to be readable, so there is no content left to hide and they do a narrower job: the
ciphertext is a short sentinel, and decrypting it is the proof you hold the
passphrase. GCM's authentication tag is what makes that a real check rather than a
comparison against a string shipped in the page. The passphrase itself is never in
the file, in any form.

**What it doesn't do.** It cannot stop someone opening devtools and editing their
own copy of a public page — nothing served statically can, and any claim otherwise
would be false. What it protects is the *published* board, and that is guarded by
the thing that actually writes it: a push to this repo. The lock's real job is
making sure the numbers your league argues about are the numbers you set.

Leave `SITE_PASSPHRASE` unset and the page builds with settings open and a badge
saying so, which is the honest state until a passphrase exists.

## The model

```
P(win)  = rating^k  / Σ rating^k
P(last) = rating^−k / Σ rating^−k
```

**k is the spread dial.** It never changes the order, only how far apart the prices
sit — and it works on *ratios*, not gaps. Rating two teams 88 and 30 is a 2.9×
ratio; 88 and 80 is 1.1× and barely separates at all. Pick a k that puts your best
team somewhere you'd actually bet (+250 to +400 in a ten-team league), then leave it
alone and move the ratings, not the model.

**Last place is not "doesn't win."** Inverting `1−p` would be wrong — it answers a
different question. The same model runs with the exponent's sign flipped, so the
worst team becomes the favourite and both boards stay internally consistent. That
inversion compresses the good teams and blows out the bad one, which is why the
last-place pool gets its own k, usually a lower one.

**Vig** multiplies every probability before it becomes a price. At 8% the implied
percentages sum to 108% and that 8% is the hold. **4.76% is the standard ten-cent
line** — −110 implies 110/210 = 52.38%, and 0.5238/0.50 = 1.0476. The slider steps
by 0.25 and the box takes any value, so exact holds are reachable.

Prices are posted first and read back second — vig, then the longshot cap, then
rounding to real board increments — and the probability and decimal columns are
derived from the *posted* price, so every column describes the bet actually on
offer. The book total counts what the cap costs on top of the vig.

**Ratings from points.** Record in fantasy is mostly schedule luck; PPG is the more
predictive number. Points mode converts to z-scores and re-centres —
`50 + 15 × (PPG − avg) / stdev` — mapping a normal league onto roughly 20–80. Fill
the Preseason column and it shrinks toward that prior by `w = games/(games+4)`,
washing out by about week 8.

## Origin

Built from a claude.ai conversation about pricing a commissioner's power rankings.
The three follow-up questions in that chat — what vig makes a coin flip −110, what
the spread actually does, and how to pick ratings — are folded in as features rather
than advice: the 0.25-step vig box, the split win/last spreads, and Points mode.
