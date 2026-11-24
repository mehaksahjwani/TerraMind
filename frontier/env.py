"""Frontier Strategy: a two-player, Catan-inspired TextArena game (v1 rules).

This file is deliberately self-contained (it imports only the standard library and
textarena) so it can be copied unchanged into SPIRAL as
``spiral/envs/FrontierStrategy/env.py``.

Layout:
  * ``FrontierGame``          - pure game rules, no TextArena dependency.
  * ``FrontierStrategyEnv``   - the ``ta.Env`` wrapper used by TextArena / SPIRAL.
  * ``parse_legal_actions``   - extracts the legal-action list from an observation;
                                SPIRAL needs this registered as the env's action parser.

See docs/rules.md for the rules and the state format.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

ROWS = "ABCD"
COLS = "1234"
CELLS: List[str] = [r + c for r in ROWS for c in COLS]  # fixed iteration order A1..D4

RESOURCES = ("wood", "stone", "food")
TERRAIN_RESOURCE = {"forest": "wood", "mountain": "stone", "plains": "food"}
RESOURCE_LETTER = {"wood": "W", "stone": "S", "food": "F"}

TERRAIN_COUNTS = {"forest": 5, "mountain": 5, "plains": 4}  # 14 resource tiles
# Production chances for the 14 resource tiles (mean 0.5). Shuffled per game.
PROBABILITIES = [0.3] * 3 + [0.4] * 3 + [0.5] * 2 + [0.6] * 3 + [0.7] * 3

STARTING_INVENTORY = {"wood": 3, "stone": 2, "food": 3}
DEFAULT_STARTS = ("B2", "C3")
DEFAULT_NUM_ROUNDS = 10

COSTS: Dict[str, Dict[str, int]] = {
    "road": {"wood": 1},
    "claim": {"stone": 1, "food": 1},
    "upgrade": {"stone": 2, "wood": 1},
    "pass": {},
}

NETWORK_BONUS = 2
NETWORK_BONUS_MIN_SETTLEMENTS = 4

ACTION_RE = re.compile(
    r"\[\s*(?:(road|claim|upgrade)\s+([A-Da-d])\s*([1-4])|(pass))\s*\]", re.IGNORECASE
)


def neighbours(cell: str) -> List[str]:
    """Orthogonal neighbours (up, down, left, right) inside the 4x4 board."""
    r, c = ROWS.index(cell[0]), COLS.index(cell[1])
    out = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < 4 and 0 <= nc < 4:
            out.append(ROWS[nr] + COLS[nc])
    return out


def format_action(kind: str, cell: Optional[str] = None) -> str:
    return "[pass]" if kind == "pass" else f"[{kind} {cell}]"


def parse_action(text: str) -> Tuple[Optional[Tuple[str, Optional[str]]], Optional[str]]:
    """Parse exactly one bracketed action from ``text``.

    Returns ``((kind, cell_or_None), None)`` on success, or ``(None, reason)``.
    Case and inner whitespace are tolerated: ``[Road b 3]`` -> ("road", "B3").
    """
    matches = list(ACTION_RE.finditer(text or ""))
    if not matches:
        return None, (
            "No valid action found. Reply with one bracketed action such as "
            "[road B3], [claim B3], [upgrade B2] or [pass]."
        )
    parsed = set()
    for m in matches:
        if m.group(4):
            parsed.add(("pass", None))
        else:
            parsed.add((m.group(1).lower(), m.group(2).upper() + m.group(3)))
    if len(parsed) > 1:
        return None, "Multiple different actions found. Reply with exactly one action."
    return parsed.pop(), None


def parse_legal_actions(observation: str) -> List[str]:
    """Return the legal actions listed on the last 'Legal actions:' line.

    Used as SPIRAL's valid-action parser and by text-only agents.
    """
    lines = [ln for ln in observation.splitlines() if ln.strip().startswith("Legal actions:")]
    if not lines:
        return ["[pass]"]
    return re.findall(r"\[[^\[\]]+\]", lines[-1])


# --------------------------------------------------------------------------- #
# Pure game logic
# --------------------------------------------------------------------------- #


class FrontierGame:
    """All rules of Frontier Strategy, independent of TextArena.

    The whole game lives in ``self.s`` (a plain, JSON-serialisable dict) plus a
    private ``random.Random`` used for board generation and production rolls.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        starts: Tuple[str, str] = DEFAULT_STARTS,
        num_rounds: int = DEFAULT_NUM_ROUNDS,
    ):
        if seed is None:
            seed = random.SystemRandom().randrange(2**63)
        assert len(starts) == 2 and starts[0] != starts[1] and all(s in CELLS for s in starts)
        self.rng = random.Random(seed)
        self.num_rounds = num_rounds
        self.s: Dict[str, Any] = {
            "seed": seed,
            "round": 1,  # 1..num_rounds
            "current_player": 0,  # player 0 always acts first in a round
            "done": False,
            "board": self._generate_board(starts),
            "players": {
                pid: {"start": starts[pid], "inventory": dict(STARTING_INVENTORY)}
                for pid in (0, 1)
            },
            "valid_turns": 0,
            "last_events": [],  # human-readable summary of the previous turn
            "board_full_round": None,  # first round in which no empty cell remained
        }

    # ---- setup ---------------------------------------------------------- #

    def _generate_board(self, starts: Tuple[str, str]) -> Dict[str, Dict[str, Any]]:
        terrains = [t for t, n in TERRAIN_COUNTS.items() for _ in range(n)]
        probs = list(PROBABILITIES)
        self.rng.shuffle(terrains)
        self.rng.shuffle(probs)
        board: Dict[str, Dict[str, Any]] = {}
        it = iter(zip(terrains, probs))
        for cell in CELLS:
            if cell in starts:
                pid = starts.index(cell)
                board[cell] = {
                    "terrain": "start", "resource": None, "prob": None,
                    "owner": pid, "building": "settlement", "upgraded": False,
                }
            else:
                terrain, prob = next(it)
                board[cell] = {
                    "terrain": terrain, "resource": TERRAIN_RESOURCE[terrain], "prob": prob,
                    "owner": None, "building": None, "upgraded": False,
                }
        return board

    # ---- queries -------------------------------------------------------- #

    @property
    def board(self) -> Dict[str, Dict[str, Any]]:
        return self.s["board"]

    def inventory(self, pid: int) -> Dict[str, int]:
        return self.s["players"][pid]["inventory"]

    def owned(self, pid: int, building: Optional[str] = None) -> List[str]:
        return [
            c for c in CELLS
            if self.board[c]["owner"] == pid and (building is None or self.board[c]["building"] == building)
        ]

    def network(self, pid: int) -> set:
        """Cells reachable from the player's start through their own roads/settlements."""
        start = self.s["players"][pid]["start"]
        seen, stack = {start}, [start]
        while stack:
            for n in neighbours(stack.pop()):
                if n not in seen and self.board[n]["owner"] == pid:
                    seen.add(n)
                    stack.append(n)
        return seen

    def can_afford(self, pid: int, kind: str) -> bool:
        inv = self.inventory(pid)
        return all(inv[r] >= n for r, n in COSTS[kind].items())

    def legal_actions(self, pid: int) -> List[Tuple[str, Optional[str]]]:
        """All legal (kind, cell) pairs for ``pid`` in a fixed, deterministic order."""
        acts: List[Tuple[str, Optional[str]]] = []
        if self.can_afford(pid, "road"):
            net = self.network(pid)
            for c in CELLS:
                if self.board[c]["owner"] is None and any(n in net for n in neighbours(c)):
                    acts.append(("road", c))
        if self.can_afford(pid, "claim"):
            acts += [("claim", c) for c in self.owned(pid, "road")]
        if self.can_afford(pid, "upgrade"):
            acts += [("upgrade", c) for c in self.owned(pid, "settlement") if not self.board[c]["upgraded"]]
        acts.append(("pass", None))
        return acts

    def validate(self, pid: int, kind: str, cell: Optional[str]) -> Optional[str]:
        """Return None if the action is legal, otherwise a reason string."""
        if self.s["done"]:
            return "The game is over."
        if pid != self.s["current_player"]:
            return f"It is Player {self.s['current_player']}'s turn."
        if kind == "pass":
            return None
        if cell not in self.board:
            return f"{cell} is not a cell on the board (A1-D4)."
        if not self.can_afford(pid, kind):
            cost = ", ".join(f"{n} {r}" for r, n in COSTS[kind].items())
            return f"You cannot afford {kind} (costs {cost})."
        tile = self.board[cell]
        if kind == "road":
            if tile["owner"] is not None:
                return f"{cell} is already occupied."
            if not any(n in self.network(pid) for n in neighbours(cell)):
                return f"{cell} is not adjacent to your network."
            return None
        if kind == "claim":
            if tile["owner"] != pid or tile["building"] != "road":
                return f"You can only claim a tile that holds your own road; {cell} does not."
            return None
        if kind == "upgrade":
            if tile["owner"] != pid or tile["building"] != "settlement":
                return f"{cell} is not one of your settlements."
            if tile["upgraded"]:
                return f"{cell} is already upgraded."
            return None
        return f"Unknown action '{kind}'."

    def settlement_count(self, pid: int) -> int:
        return len(self.owned(pid, "settlement"))

    def score(self, pid: int) -> int:
        settlements = self.owned(pid, "settlement")
        upgrades = sum(1 for c in settlements if self.board[c]["upgraded"])
        # Count only settlements connected to the start through own cells. (In v1 every
        # owned cell is always connected, but this keeps the rule explicit.)
        net = self.network(pid)
        connected = sum(1 for c in settlements if c in net)
        bonus = NETWORK_BONUS if connected >= NETWORK_BONUS_MIN_SETTLEMENTS else 0
        return len(settlements) + upgrades + bonus

    def total_resources(self, pid: int) -> int:
        return sum(self.inventory(pid).values())

    def empty_cells(self) -> List[str]:
        return [c for c in CELLS if self.board[c]["owner"] is None]

    # ---- transitions ---------------------------------------------------- #

    def apply(self, pid: int, kind: str, cell: Optional[str]) -> List[str]:
        """Apply a legal action. Raises ValueError (state untouched) if it is illegal.

        Returns a list of event strings describing what happened (action, and the
        production roll / game end if this action closed a round).
        """
        reason = self.validate(pid, kind, cell)
        if reason is not None:
            raise ValueError(reason)

        inv = self.inventory(pid)
        for r, n in COSTS[kind].items():
            inv[r] -= n
        if kind == "road":
            self.board[cell].update(owner=pid, building="road")
        elif kind == "claim":
            self.board[cell]["building"] = "settlement"
        elif kind == "upgrade":
            self.board[cell]["upgraded"] = True

        self.s["valid_turns"] += 1
        events = [f"Player {pid} played {format_action(kind, cell)}."]

        if self.s["board_full_round"] is None and not self.empty_cells():
            self.s["board_full_round"] = self.s["round"]

        if pid == 0:
            self.s["current_player"] = 1
        else:  # both players have acted: end of round
            if self.s["round"] < self.num_rounds:
                events.append(self._produce())
                self.s["round"] += 1
                self.s["current_player"] = 0
            else:
                self.s["done"] = True
                events.append("Round limit reached; final scores are counted.")
        self.s["last_events"] = events
        return events

    def _produce(self) -> str:
        """Roll every settlement on a resource tile once, in fixed cell order."""
        gains = {0: [], 1: []}
        for c in CELLS:
            t = self.board[c]
            if t["building"] != "settlement" or t["resource"] is None:
                continue  # roads, empty tiles and start settlements never produce
            if self.rng.random() < t["prob"]:
                amount = 2 if t["upgraded"] else 1
                self.inventory(t["owner"])[t["resource"]] += amount
                gains[t["owner"]].append(f"+{amount} {t['resource']} ({c})")
        parts = [
            f"P{pid} " + (", ".join(gains[pid]) if gains[pid] else "nothing") for pid in (0, 1)
        ]
        return f"Production after round {self.s['round']}: " + "; ".join(parts) + "."

    def outcome(self) -> Tuple[Optional[int], str]:
        """(winner or None for draw, reason). Only meaningful once the game is done."""
        sc = {p: self.score(p) for p in (0, 1)}
        st = {p: self.settlement_count(p) for p in (0, 1)}
        rs = {p: self.total_resources(p) for p in (0, 1)}
        summary = f"Final scores P0={sc[0]}, P1={sc[1]}"
        for metric, name in ((sc, "higher score"), (st, "more settlements"), (rs, "more leftover resources")):
            if metric[0] != metric[1]:
                w = 0 if metric[0] > metric[1] else 1
                if name == "higher score":
                    return w, f"Player {w} wins with the {name}. {summary}."
                return w, (
                    f"Player {w} wins the tie-break with {name} "
                    f"({metric[w]} vs {metric[1 - w]}). {summary}."
                )
        return None, f"Draw: equal score, settlements and leftover resources. {summary}."

    # ---- rendering ------------------------------------------------------ #

    def cell_token(self, cell: str) -> str:
        t = self.board[cell]
        if t["terrain"] == "start":
            return f"P{t['owner']}{'*' if t['upgraded'] else ''}base"
        tile = f"{RESOURCE_LETTER[t['resource']]}{int(round(t['prob'] * 100))}"
        if t["building"] == "road":
            return f"{tile}:r{t['owner']}"
        if t["building"] == "settlement":
            return f"{tile}:P{t['owner']}{'*' if t['upgraded'] else ''}"
        return tile

    def render_board(self) -> str:
        w = 9
        lines = ["   " + "".join(c.ljust(w) for c in COLS).rstrip()]
        for r in ROWS:
            lines.append(f"{r}  " + "".join(self.cell_token(r + c).ljust(w) for c in COLS).rstrip())
        return "\n".join(lines)

    def render_for(self, pid: int) -> str:
        """Compact state text for ``pid``. The last line lists the legal actions."""
        opp = 1 - pid
        inv = lambda p: ", ".join(f"{r}={self.inventory(p)[r]}" for r in RESOURCES)  # noqa: E731
        order = "you act first" if pid == 0 else "you act second"
        lines = [f"FRONTIER STRATEGY - You are Player {pid} - Round {self.s['round']}/{self.num_rounds} ({order})"]
        if self.s["last_events"]:
            lines.append("Last turn: " + " ".join(self.s["last_events"]))
        lines += [
            f"Your resources: {inv(pid)}",
            f"Opponent resources: {inv(opp)}",
            f"Scores: You={self.score(pid)} ({self.settlement_count(pid)} settlements), "
            f"Opponent={self.score(opp)} ({self.settlement_count(opp)} settlements)",
            "Board (W/S/F = wood/stone/food tile + production %, r0/r1 = road, "
            "P0/P1 = settlement, * = upgraded, base = starting settlement):",
            self.render_board(),
            "Legal actions: " + ", ".join(format_action(k, c) for k, c in self.legal_actions(pid)),
        ]
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# TextArena environment
# --------------------------------------------------------------------------- #


class FrontierStrategyEnv(ta.Env):
    """TextArena wrapper around ``FrontierGame``, modelled on SPIRAL's PigDice env.

    Each turn the acting player receives ONE message containing the full current
    state and the legal-action list, so it works with SPIRAL's
    FirstLastObservationWrapper (rules prompt + latest message).
    """

    def __init__(
        self,
        num_rounds: int = DEFAULT_NUM_ROUNDS,
        starts: Tuple[str, str] = DEFAULT_STARTS,
    ):
        super().__init__()
        self.num_rounds = num_rounds
        self.starts = tuple(starts)
        self.game: Optional[FrontierGame] = None

    def reset(self, num_players: int, seed: Optional[int] = None) -> None:
        self.game = FrontierGame(seed=seed, starts=self.starts, num_rounds=self.num_rounds)
        self.state = ta.State(
            num_players=num_players,
            min_players=2,
            max_players=2,
            max_turns=2 * self.num_rounds,
            check_truncated=False,  # the game ends itself after the last round
            role_mapping={},  # avoid textarena's shared mutable default
        )
        # Note: ta.State.reset reseeds Python's *global* RNG; our game uses its own RNG.
        self.state.reset(seed=seed, game_state=self.game.s, player_prompt_function=self._player_prompt)
        self._send_state(0)

    def _player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in Frontier Strategy, a two-player game on a 4x4 grid "
            f"(rows A-D, columns 1-4; only up/down/left/right are adjacent).\n"
            f"Each tile produces wood (W), stone (S) or food (F) with the shown % chance per round.\n"
            f"Actions (one per turn):\n"
            f"- [road X]: 1 wood. Place a road on an empty tile next to your network "
            f"(your starting base plus your roads and settlements).\n"
            f"- [claim X]: 1 stone + 1 food. Turn your road on X into a settlement.\n"
            f"- [upgrade X]: 2 stone + 1 wood. Upgrade one of your settlements once (+1 point, "
            f"it then produces 2 instead of 1).\n"
            f"- [pass]: do nothing.\n"
            f"After both players act, each settlement on a resource tile rolls its % chance and "
            f"gives its owner 1 unit (2 if upgraded). Bases and roads never produce. "
            f"There are {self.num_rounds} rounds; there is no production after the last one.\n"
            f"Scoring: +1 per settlement (including your base), +1 per upgrade, +2 once for 4 or more "
            f"connected settlements. Higher score wins; ties go to more settlements, then more "
            f"leftover resources.\n"
            f"Tiles taken by the opponent are blocked. An invalid action loses the game.\n"
            f"Reply with exactly one action copied from the Legal actions list, e.g. [road B3]."
        )

    def _send_state(self, pid: int, prefix: str = "") -> None:
        self.state.add_observation(from_id=ta.GAME_ID, to_id=pid, message=prefix + self.game.render_for(pid))

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        pid = self.state.current_player_id
        parsed, reason = parse_action(action)
        if parsed is not None:
            reason = self.game.validate(pid, *parsed)

        if reason is not None:
            self.state.set_invalid_move(player_id=pid, reason=reason)
            if not self.state.done:  # a retry is allowed: show the unchanged state again
                self._send_state(pid, prefix=f"Your action was invalid: {reason}\n")
            return self.state.step(rotate_player=False)

        self.game.apply(pid, *parsed)

        if self.game.s["done"]:
            winner, why = self.game.outcome()
            if winner is None:
                self.state.set_draw(reason=why)
            else:
                self.state.set_winners(player_ids=[winner], reason=why)
        else:
            self._send_state(self.game.s["current_player"])
        return self.state.step(rotate_player=True)

    def get_board_str(self) -> str:
        return self.game.render_board()

    def snapshot(self) -> Dict[str, Any]:
        """Deep copy of the game state (for tests and debugging)."""
        return copy.deepcopy(self.game.s)
