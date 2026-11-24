"""Run many Frontier Strategy games between baseline agents and print balance stats.

Games are played through the real TextArena env (ta.make + FirstLastObservationWrapper),
so this also checks the env never crashes or rejects a legal move.

Usage:
    python scripts/simulate.py                       # 1000 games for each matchup
    python scripts/simulate.py --games 200 --starts A1 D4
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import textarena as ta  # noqa: E402

import frontier  # noqa: E402,F401  (registers FrontierStrategy-v0)
from agents import AGENTS  # noqa: E402


def play(p0, p1, seed, starts):
    env = ta.wrappers.FirstLastObservationWrapper(ta.make("FrontierStrategy-v0", starts=tuple(starts)))
    env.reset(num_players=2, seed=seed)
    game = env.env.game
    agents = {0: p0, 1: p1}
    passes, forced, actions, done = Counter(), Counter(), 0, False
    while not done:
        pid, _obs = env.get_observation()
        forced[pid] += len(game.legal_actions(pid)) == 1
        action = agents[pid](game, pid)
        passes[pid] += action == "[pass]"
        done, info = env.step(action)
        actions += 1
    rewards = env.close()
    if "Invalid" in str(info.get("reason", "")):
        raise RuntimeError(f"seed {seed}: legal action rejected: {info}")
    return {
        "rewards": rewards,
        "scores": (game.score(0), game.score(1)),
        "actions": actions,
        "passes": passes,
        "forced": forced,
        "full_round": game.s["board_full_round"],
        "tiebreak": "tie-break" in info.get("reason", ""),
    }


def run_matchup(name0, name1, games, starts, seed0=0):
    results = []
    for g in range(games):
        a0 = AGENTS[name0](seed=10_000 + g)
        a1 = AGENTS[name1](seed=20_000 + g)
        results.append(play(a0, a1, seed=seed0 + g, starts=starts))
    n = len(results)
    wins0 = sum(r["rewards"][0] == 1 for r in results)
    wins1 = sum(r["rewards"][1] == 1 for r in results)
    draws = n - wins0 - wins1
    full = [r["full_round"] for r in results if r["full_round"] is not None]
    bad_len = sum(r["actions"] != 20 for r in results)
    print(f"\n{name0} (P0) vs {name1} (P1), {n} games, starts {starts[0]}/{starts[1]}")
    print(f"  P0 win {100 * wins0 / n:5.1f}%   P1 win {100 * wins1 / n:5.1f}%   draw {100 * draws / n:5.1f}%"
          f"   (decided by tie-break: {100 * sum(r['tiebreak'] for r in results) / n:.1f}%)")
    print(f"  mean final score P0 {statistics.mean(r['scores'][0] for r in results):.2f}"
          f"   P1 {statistics.mean(r['scores'][1] for r in results):.2f}")
    print(f"  pass rate P0 {100 * sum(r['passes'][0] for r in results) / (10 * n):.1f}%"
          f"   P1 {100 * sum(r['passes'][1] for r in results) / (10 * n):.1f}%")
    print(f"  forced pass (only [pass] legal) P0 {100 * sum(r['forced'][0] for r in results) / (10 * n):.1f}%"
          f"   P1 {100 * sum(r['forced'][1] for r in results) / (10 * n):.1f}%")
    if full:
        print(f"  board filled in {100 * len(full) / n:.1f}% of games, mean round {statistics.mean(full):.1f}")
    else:
        print("  board never filled")
    print(f"  games not exactly 20 actions: {bad_len}")
    return wins0, wins1, draws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--starts", nargs=2, default=["B2", "C3"])
    args = ap.parse_args()
    matchups = [("random", "random"), ("greedy", "random"), ("random", "greedy"), ("greedy", "greedy"),
                ("builder", "random"), ("random", "builder"), ("builder", "greedy"), ("builder", "builder")]
    for a, b in matchups:
        run_matchup(a, b, args.games, args.starts)


if __name__ == "__main__":
    main()
