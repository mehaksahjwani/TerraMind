# Frontier Strategy — v1 rules and state format

Two players build the best settlement network on a 4×4 grid. The game is designed to
combine spatial, probabilistic and strategic reasoning in one decision. This file is
the reference for `frontier/env.py`; if the two disagree, fix one of them.

## Board and setup

- 4×4 grid, rows A–D, columns 1–4 (`A1` … `D4`). Only up/down/left/right are adjacent.
- Player 0 starts with a settlement at **B2**, Player 1 at **C3** (configurable via
  `starts=`). Starting settlements (bases) never produce.
- The other 14 cells: 5 forest (wood), 5 mountain (stone), 4 plains (food), shuffled.
- Each resource tile gets a fixed production chance. The 14 chances are the multiset
  `30% ×3, 40% ×3, 50% ×2, 60% ×3, 70% ×3` (mean 50%), shuffled independently of terrain.
- Each player starts with **3 wood, 2 stone, 3 food**.
- Everything is public: tiles, chances, ownership, inventories, scores.

## Actions (one per turn)

| Action | Cost | Rule |
| --- | --- | --- |
| `[road X]` | 1 wood | X is empty and orthogonally adjacent to your network (base + your roads + your settlements). |
| `[claim X]` | 1 stone + 1 food | X holds your own road; it becomes a settlement. |
| `[upgrade X]` | 2 stone + 1 wood | X is one of your claimed settlements (not your base) and not yet upgraded. +1 point; it then produces 2 instead of 1. |
| `[pass]` | — | Always legal. |

- A cell has at most one owner. You cannot build on, or extend through, the opponent's cells.
- You may build past your own unclaimed road.
- Parsing accepts any case and extra spaces (`[Road b 3]`), but a reply containing two
  *different* actions is invalid. SPIRAL is stricter: it only accepts a reply whose
  extracted action is exactly one of the listed strings (e.g. `[road B3]`).

## Turn order and production

- 10 rounds. In each round Player 0 acts, then Player 1 (20 valid actions per game).
- After both players act in rounds 1–9, every settlement on a resource tile rolls its
  chance once (cells in order A1…D4) and gives its owner 1 unit, or 2 if upgraded.
  A tile claimed earlier in the same round takes part. Roads and bases never produce.
- After round 10 there is no production and the game is scored.

## Scoring and winner

- +1 per settlement (including the base), +1 per upgraded settlement.
- +2 once if you have at least 4 settlements connected to your base through your own
  cells. (In v1 every owned cell is always connected, so this is "4+ settlements".)
- Roads and leftover resources score 0.
- Higher score wins. Ties: more settlements, then more total leftover resources, then draw.
- Rewards: winner +1, loser −1, draw 0 / 0.

## Invalid moves

The game rejects an invalid move without changing anything (board, inventories,
production RNG, turn counter) and calls TextArena's `state.set_invalid_move`.

- **Plain TextArena (`error_allowance=1`)**: one retry. The player sees the reason and
  the unchanged state again. A second invalid move ends the game with rewards
  offender −1, opponent **0** (TextArena 0.6.4 behaviour, not +1).
- **SPIRAL training**: SPIRAL sets `error_allowance = 0`. It also checks the model's
  reply against the legal-action list itself. A reply that isn't on the list becomes
  `INVALID_ACTION` and the game ends with offender **−1.5**, opponent **+0.5**.

## What the model sees

With `FirstLastObservationWrapper` (`--use_llm_obs_wrappers False`), the model sees the
rules prompt plus only the latest message. So each turn the acting player gets one
message containing the full state:

```
FRONTIER STRATEGY - You are Player 0 - Round 3/10 (you act first)
Last turn: Player 1 played [claim D3]. Production after round 2: P0 nothing; P1 +1 wood (D3).
Your resources: wood=2, stone=2, food=3
Opponent resources: wood=3, stone=1, food=2
Scores: You=1 (1 settlements), Opponent=2 (2 settlements)
Board (W/S/F = wood/stone/food tile + production %, r0/r1 = road, P0/P1 = settlement, * = upgraded, base = starting settlement):
   1        2        3        4
A  W60      F40      F30      S60
B  S50      P0base   W40:r0   F30
C  S70      W60      P1base   W70
D  F40      S30      W70:P1   S50
Legal actions: [road A2], [road A3], [road B1], [road B4], [road C2], [claim B3], [upgrade B2], [pass]
```

The last line is what SPIRAL's action parser (`parse_legal_actions`) reads.

## State format (to agree on)

`FrontierGame.s` is a plain, JSON-serialisable dict; `FrontierStrategyEnv` passes the
same object to `ta.State` as `game_state`. Score is always derived from the board,
never stored, so it can't drift out of sync.

```python
{
  "seed": 123,                 # per-game seed; one private random.Random(seed) drives
                               # board generation, then production rolls
  "round": 1,                  # 1..10
  "current_player": 0,         # 0 acts first in every round
  "done": False,
  "valid_turns": 0,            # accepted actions so far (20 at the end)
  "board_full_round": None,    # first round with no empty cell (balance metric)
  "last_events": [...],        # text summary shown as "Last turn:"
  "players": {
    0: {"start": "B2", "inventory": {"wood": 3, "stone": 2, "food": 3}},
    1: {"start": "C3", "inventory": {"wood": 3, "stone": 2, "food": 3}},
  },
  "board": {                   # all 16 cells, keys "A1".."D4"
    "B3": {"terrain": "mountain",   # forest | mountain | plains | start
           "resource": "stone",     # wood | stone | food | None (start)
           "prob": 0.7,             # None for starts
           "owner": None,           # None | 0 | 1
           "building": None,        # None | "road" | "settlement"
           "upgraded": False},
    ...
  },
}
```

Note: `ta.State.reset(seed=...)` reseeds Python's *global* `random`; the game never
uses the global RNG, so that has no effect on the game.

## Balance results so far

`python scripts/simulate.py` (1,000 games per matchup, starts B2/C3):

| Matchup (P0 vs P1) | P0 win | P1 win | Draw | Mean score | Notes |
| --- | ---: | ---: | ---: | --- | --- |
| random vs random | 48.0% | 46.1% | 5.9% | 4.33 / 4.30 | |
| greedy vs random | 62.9% | 35.2% | 1.9% | 4.87 / 4.42 | |
| builder vs random | 70.1% | 28.1% | 1.8% | 5.61 / 4.43 | |
| builder vs greedy | 56.2% | 42.0% | 1.8% | 5.61 / 4.99 | |
| builder vs builder | 49.9% | 48.8% | 1.3% | 5.61 / 5.65 | |

These are after making bases un-upgradable. Before that change, greedy won 0% against
random (it upgraded its base in round 1, spent all its stone, and was stuck at 2 points).

Starts A1/D4 with random vs random gave 35.9 / 34.5 / 29.6% draws, so B2/C3 is kept.

**Open design questions for the team**

1. *Resolved: bases cannot be upgraded.* Upgrading the base used to give +1 point but
   spent all the starting stone, and since bases never produce, that player could never
   claim again. Now only claimed (producing) tiles can be upgraded, so choosing which
   tile to upgrade depends on its production chance. Greedy now beats random ~63%.
2. *The economy is tight.* With random play, a third of turns allow only `[pass]`, and
   the board fills in under 1% of games. So "round the board fills up" is not a useful
   metric yet, and blocking rarely matters. Consider more starting resources or
   higher chances if you want more spatial competition.
3. The `builder` agent (`scripts/agents.py`) is not in the plan. It was added to show
   that planning is rewarded; it beats random 84% and the mirror match is even.
