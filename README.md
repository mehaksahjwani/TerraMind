# TerraMind — Frontier Strategy

A two-player, Catan-inspired game built on [TextArena](https://github.com/LeonGuertler/TextArena) for LLM self-play training with [SPIRAL](https://github.com/spiral-rl/spiral). It combines spatial, probabilistic and strategic reasoning in one game, to test whether training on it improves reasoning benchmarks compared with SPIRAL's three-game mixture.

Rules and state format: [docs/rules.md](docs/rules.md).

## Layout

```
frontier/env.py        the game: FrontierGame (rules) + FrontierStrategyEnv (ta.Env)
frontier/__init__.py   registers FrontierStrategy-v0 for local use
scripts/agents.py      random, greedy and builder baseline players
scripts/simulate.py    1,000-game balance stats per matchup
scripts/play_human.py  play in the terminal (same view the LLM gets)
tests/test_rules.py    rule tests
narval/                SPIRAL integration on Narval (setup, check, smoke run)
```

`frontier/env.py` imports only textarena and the standard library, so it can be copied unchanged into SPIRAL as `spiral/envs/FrontierStrategy/env.py`.

## Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                       # rule tests
python scripts/simulate.py --games 1000   # balance stats
python scripts/play_human.py              # you vs a random bot
python scripts/play_human.py --opponent builder --seed 7
```

## Narval (SPIRAL)

```bash
cd ~/frontier-strategy            # this repo
bash narval/setup_envs.sh         # copies SPIRAL envs/ + agents/ to $SCRATCH and patches them
bash narval/check_env.sh          # loads the game inside the container, plays one random game
sbatch narval/job_smoke.sh        # short training run (fill in the CHECK lines first)
```

`setup_envs.sh` patches two things. It registers `FrontierStrategy-v0` in `spiral/envs/__init__.py`. It also adds its legal-action parser to `spiral/agents/utils.py`; SPIRAL's training loop needs a parser for every env and raises `NotImplementedError` without one. The image itself is never modified. The patched folders are bind-mounted over the originals.
