"""Play Frontier Strategy in the terminal.

Shows exactly what the LLM sees under SPIRAL (FirstLastObservationWrapper:
rules prompt + latest state message).

Usage:
    python scripts/play_human.py                      # you (P0) vs random bot (P1)
    python scripts/play_human.py --opponent human     # two humans, hot-seat
    python scripts/play_human.py --opponent builder --seat 1 --seed 7
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import textarena as ta  # noqa: E402

import frontier  # noqa: E402,F401
from agents import AGENTS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opponent", default="random", choices=["human", *AGENTS])
    ap.add_argument("--seat", type=int, default=0, choices=[0, 1], help="your player id")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--retries", type=int, default=1, help="invalid moves allowed per turn (SPIRAL training uses 0)")
    args = ap.parse_args()

    env = ta.wrappers.FirstLastObservationWrapper(ta.make("FrontierStrategy-v0"))
    env.reset(num_players=2, seed=args.seed)
    env.state.error_allowance = args.retries
    game = env.env.game

    human = ta.agents.HumanAgent()
    bot = None if args.opponent == "human" else AGENTS[args.opponent](seed=args.seed)

    done = False
    while not done:
        pid, obs = env.get_observation()
        if bot is None or pid == args.seat:
            print("\n" + "=" * 70)
            action = human(obs)
        else:
            action = bot(game, pid)
            print(f"\n[Player {pid} ({args.opponent}) plays {action}]")
        done, info = env.step(action)

    print("\n" + "=" * 70)
    print(env.get_board_str())
    print(info.get("reason"))
    print("Rewards:", env.close())


if __name__ == "__main__":
    main()
