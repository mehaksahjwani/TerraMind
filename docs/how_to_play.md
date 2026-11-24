# How to play Frontier Strategy

Frontier Strategy is a short two-player strategy game on a 4×4 grid. You and your
opponent race to build the best network of settlements. You spend wood, stone and
food to expand, and your settlements earn more resources by chance each round. After
10 rounds, the player with the higher score wins.

It was built to train and test AI models, but it plays fine between people too.

## Goal

Have more points than your opponent at the end of round 10.

- **+1** for each settlement you own (your starting base counts)
- **+1** for each upgraded settlement
- **+2** once, if you own 4 or more settlements

Roads and leftover resources are worth nothing. If scores are tied, the player with
more settlements wins, then the player with more leftover resources. Otherwise it's a draw.

## Reading the board

```
   1        2        3        4
A  W60      F40      F30      S60
B  S50      P0base   W40:r0   F30
C  S70      W60      P1base   W70
D  F40      S30      W70:P1   S50
```

- Each cell has a name like `B3` (row letter, column number).
- `W` / `S` / `F` is the tile's resource: **wood**, **stone** or **food**.
- The number is its chance (in %) of producing each round. `W60` = a 60% wood tile.
- `P0base` / `P1base` are the starting bases. They never produce anything.
- `:r0` = Player 0's road, `:P1` = Player 1's settlement, `*` = upgraded.

## On your turn, choose one action

| Type this | Costs | What it does |
| --- | --- | --- |
| `[road B3]` | 1 wood | Puts your road on an empty tile next to your base, roads or settlements. Reserves the tile. |
| `[claim B3]` | 1 stone + 1 food | Turns your road into a settlement: +1 point, and it starts producing. |
| `[upgrade B3]` | 2 stone + 1 wood | Upgrades a settlement once: +1 point, and it now produces 2 instead of 1. |
| `[pass]` | free | Do nothing and save your resources. |

- Only up/down/left/right count as next to. Diagonals don't.
- You can't build on, or through, your opponent's tiles, so a road can block them.
- The game shows your **Legal actions** every turn. Pick one of those.

You start with **3 wood, 2 stone, 3 food**.

## How a round works

1. Player 0 acts, then Player 1 acts.
2. After both have acted (rounds 1–9), every settlement rolls its chance. On a success,
   its owner gets 1 of that resource, or 2 if upgraded.
3. After round 10 there's no roll. Scores are counted and the winner is announced.

## A few tips

- Stone is scarce: you start with only 2, and both claiming and upgrading need it.
- Upgrading your base gives a quick point, but bases never produce. That stone can't
  then pay for a claim.
- Claim early. A 70% tile claimed in round 2 gets 8 rolls; claimed in round 8, only 2.
- A cheap road on a tile your opponent wants can cut off their expansion.

## Play it

```bash
pip install -r requirements.txt
python scripts/play_human.py                       # you vs a random bot
python scripts/play_human.py --opponent builder    # a stronger bot
python scripts/play_human.py --opponent human      # two players, one keyboard
```

Type an action such as `[road B3]` and press Enter. One invalid move gets a warning;
a second one loses the game. Full rules: [rules.md](rules.md).
