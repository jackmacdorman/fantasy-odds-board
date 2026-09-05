# League Odds Board

A commissioner's tool that turns fantasy power ratings into a two-sided betting
market — odds to win the league, and odds to finish last.

**Live:** https://jackmacdorman.github.io/fantasy-odds-board/

One self-contained `index.html`. No build, no dependencies, no server.

## The model

Ratings become probabilities through a Luce model:

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
by 0.25 and the box takes any value, so exact holds are reachable. For a friendly
league, 0% usually plays better.

## What it does

- **Both markets at once**, each with its own spread, priced off one set of ratings.
- **Vig presets** — fair, −110 (4.76%), and 8% — plus any value you type.
- **Longshot cap.** +2500 is a 3.85% implied floor; anything longer gets lifted to
  it. The book total tells you how much hold that costs on top of your vig, so the
  imbalance you're eating is a number rather than a shrug.
- **Tidy prices** round to the increments a real board quotes — nearest 5 up to 400,
  then 10, then 25. Probabilities are read back off the posted price, so every
  column describes the bet actually on offer.
- **Ratings from points scored.** Record in fantasy is mostly schedule luck; PPG is
  the more predictive number. Points mode converts to z-scores and re-centres —
  `50 + 15 × (PPG − avg) / stdev` — which maps a normal league onto roughly 20–80.
  Fill the Preseason column and it shrinks toward that prior by `w = games/(games+4)`,
  washing out by about week 8.
- **Paste a team list**, `Name, number` per line.
- **Copy board** gives plain text formatted for a league group chat.
- **Copy link** packs the entire board into the URL — nothing uploaded, no account.
  Anyone who opens it sees exactly your inputs, which is the healthier fight to have.

Work is kept in `localStorage`; a shared link always wins over what's stored.

## Origin

Built from a conversation about pricing a commissioner's power rankings. The three
follow-up questions in that chat — what vig makes a coin flip −110, what the spread
actually does, and how to pick ratings — are folded in here as features rather than
advice: the 0.25-step vig box, the split win/last spreads, and Points mode.
