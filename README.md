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

A build is only needed for things baked into the page: ESPN data, the passphrase,
and the app itself. Ratings and per-league settings are published from the page
itself — see below.

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

## Publishing from the page

Every league keeps its own dials — spread, vig, cap, rounding, ratings mode — plus
its own ratings. They live in **`board.json`**, and the page **fetches that at
runtime rather than baking it in**. That is the whole trick: publishing changes the
live site for everyone without anyone running a build.

Unlock the settings, edit, and press **Publish**. The page writes `board.json`
straight to this repo through the GitHub contents API and Pages redeploys, usually
within a minute. Publish carries a dot whenever this browser holds something the
live site hasn't seen.

It needs a **fine-grained personal access token**, this repo only, *Contents: read
and write*. The token is entered in the page, kept in `sessionStorage` (or
`localStorage` if you tick "remember on this device"), and sent only to
`api.github.com`. It is never committed and never baked into the build. Treat it as
a real credential: it can write to a repo whose page your league loads, so give it a
short expiry, and don't tick "remember" on a shared machine. **Copy JSON instead**
is the no-token path — it copies the file for you to commit by hand.

Concurrency is handled by the blob sha: if another device published since your page
loaded, the write is refused rather than silently overwriting, and you're told to
reload and redo.

Only leagues you actually edited are rewritten; the rest pass through exactly as
published, so editing one board can never quietly reset the other three. Owner and
PPG are always re-attached from ESPN by team id, so a stale published file can never
win on facts it doesn't own.

**A published board beats a device's local copy.** `board.json` carries an `updated`
timestamp; anything saved locally before it is discarded on load. Without that, the
laptop you last edited on would keep showing its own board forever — which is the
exact problem publishing exists to solve. Viewers never write local state at all.

Ratings are keyed by **ESPN team id**, not name, so a mid-season rename doesn't
orphan one. Anything missing defaults to 50.

Rows sort by the win market, favourite first. The sort is computed on the fair
probability rather than the posted price, so teams pinned together at the longshot
cap still come out in the right order, and it holds still while a row is being typed
into.

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
would be false. What it protects is the *published* board.

Since Publish landed, that protection has real teeth. Bypassing the lock in devtools
gets you a board only you can see: writing `board.json` needs a GitHub token with
write access to this repo, and that is never in the page. So the lock is the
convenience layer, and the token is the actual boundary — which is the right way
round, because the token is the thing that can change what your league sees.

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
