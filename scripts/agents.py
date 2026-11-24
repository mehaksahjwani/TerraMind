"""Baseline players for Frontier Strategy.

Each agent is called with the FrontierGame and the acting player id and returns an
action string such as "[road B3]". They only ever choose legal actions.
"""

from __future__ import annotations

import random
from typing import Optional

from frontier.env import FrontierGame, format_action


class RandomAgent:
    """Uniformly random legal action (including [pass])."""

    name = "random"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def __call__(self, game: FrontierGame, pid: int) -> str:
        return format_action(*self.rng.choice(game.legal_actions(pid)))


class GreedyAgent:
    """Picks the move that adds the most score right now.

    Ties are broken by: prefer building over passing, then the tile's production
    chance (roads on better tiles first), then randomly.
    """

    name = "greedy"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def __call__(self, game: FrontierGame, pid: int) -> str:
        def key(action):
            kind, cell = action
            gain = 1 if kind in ("claim", "upgrade") else 0
            builds = 0 if kind == "pass" else 1
            prob = (game.board[cell]["prob"] or 0.0) if cell else 0.0
            return (gain, builds, prob, self.rng.random())

        return format_action(*max(game.legal_actions(pid), key=key))


class BuilderAgent:
    """A simple hand-written strategy (not part of the plan; used to check that
    planning beats random play):

    1. claim the best-probability road it owns;
    2. upgrade its best *producing* settlement (never the base);
    3. build a road on the best-probability reachable tile, preferring stone/food
       tiles while it owns none of that resource type;
    4. otherwise pass.
    """

    name = "builder"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def __call__(self, game: FrontierGame, pid: int) -> str:
        legal = game.legal_actions(pid)
        prob = lambda c: game.board[c]["prob"] or 0.0  # noqa: E731
        claims = [c for k, c in legal if k == "claim"]
        if claims:
            return format_action("claim", max(claims, key=prob))
        ups = [c for k, c in legal if k == "upgrade" and game.board[c]["resource"]]
        if ups:
            return format_action("upgrade", max(ups, key=prob))
        roads = [c for k, c in legal if k == "road"]
        if roads and game.can_afford(pid, "road"):
            owned_res = {game.board[c]["resource"] for c in game.owned(pid, "settlement")}
            want = lambda c: game.board[c]["resource"] not in owned_res  # noqa: E731
            return format_action("road", max(roads, key=lambda c: (want(c), prob(c), self.rng.random())))
        return "[pass]"


AGENTS = {"random": RandomAgent, "greedy": GreedyAgent, "builder": BuilderAgent}
