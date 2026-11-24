"""Automatic checks for each Frontier Strategy rule (docs/rules.md)."""

import os
import random
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import textarena as ta  # noqa: E402

import frontier  # noqa: E402,F401
from frontier.env import (  # noqa: E402
    CELLS, FrontierGame, neighbours, parse_action, parse_legal_actions,
)


# ---------- helpers ---------------------------------------------------------- #

def blank_game(seed=0):
    """A game whose 14 resource tiles are all 50% stone and empty, for hand-built scenarios."""
    g = FrontierGame(seed=seed)
    for c in CELLS:
        t = g.board[c]
        if t["terrain"] != "start":
            t.update(terrain="mountain", resource="stone", prob=0.5)
    return g


def set_tile(g, cell, owner=None, building=None, upgraded=False, resource="stone", prob=0.5):
    terrain = {"wood": "forest", "stone": "mountain", "food": "plains"}[resource]
    g.board[cell].update(terrain=terrain, resource=resource, prob=prob,
                         owner=owner, building=building, upgraded=upgraded)


def make_env(seed=0, allowance=None):
    env = ta.make("FrontierStrategy-v0")
    env.reset(num_players=2, seed=seed)
    if allowance is not None:
        env.state.error_allowance = allowance
    return env


# ---------- board ------------------------------------------------------------ #

def test_board_composition_and_starts():
    for seed in range(50):
        g = FrontierGame(seed=seed)
        terr = Counter(g.board[c]["terrain"] for c in CELLS)
        assert terr == {"forest": 5, "mountain": 5, "plains": 4, "start": 2}
        probs = sorted(g.board[c]["prob"] for c in CELLS if g.board[c]["prob"] is not None)
        assert probs == sorted([0.3] * 3 + [0.4] * 3 + [0.5] * 2 + [0.6] * 3 + [0.7] * 3)
        assert g.board["B2"]["owner"] == 0 and g.board["C3"]["owner"] == 1
        assert g.board["B2"]["building"] == "settlement" and g.board["B2"]["resource"] is None
        assert g.inventory(0) == {"wood": 3, "stone": 2, "food": 3} == g.inventory(1)


def test_neighbours_are_orthogonal_only():
    assert sorted(neighbours("A1")) == ["A2", "B1"]
    assert sorted(neighbours("B2")) == ["A2", "B1", "B3", "C2"]
    assert "C3" not in neighbours("B2")  # diagonal


def test_same_seed_same_board_different_seed_differs():
    assert FrontierGame(seed=42).board == FrontierGame(seed=42).board
    assert any(FrontierGame(seed=s).board != FrontierGame(seed=42).board for s in range(5))


# ---------- costs & actions -------------------------------------------------- #

@pytest.mark.parametrize("kind,cell,setup,expected", [
    ("road", "B3", None, {"wood": 2, "stone": 2, "food": 3}),
    ("claim", "B3", "road", {"wood": 3, "stone": 1, "food": 2}),
    ("upgrade", "B2", None, {"wood": 2, "stone": 0, "food": 3}),
    ("pass", None, None, {"wood": 3, "stone": 2, "food": 3}),
])
def test_action_costs(kind, cell, setup, expected):
    g = blank_game()
    if setup == "road":
        set_tile(g, "B3", owner=0, building="road")
    g.apply(0, kind, cell)
    assert g.inventory(0) == expected


def test_road_claim_upgrade_effects_and_points():
    g = blank_game()
    assert g.score(0) == 1  # base only
    g.apply(0, "road", "B3")
    assert g.board["B3"]["owner"] == 0 and g.board["B3"]["building"] == "road"
    assert g.score(0) == 1  # roads give 0 points
    g.apply(1, "pass", None)
    g.apply(0, "claim", "B3")
    assert g.board["B3"]["building"] == "settlement" and g.score(0) == 2
    g.inventory(0).update(stone=2, wood=1)
    g.apply(1, "pass", None)
    g.apply(0, "upgrade", "B3")
    assert g.board["B3"]["upgraded"] and g.score(0) == 3


def test_unaffordable_actions_rejected_and_not_listed():
    g = blank_game()
    g.inventory(0).update(wood=0, stone=0, food=0)
    set_tile(g, "B3", owner=0, building="road")
    assert g.legal_actions(0) == [("pass", None)]
    for kind, cell in [("road", "A2"), ("claim", "B3"), ("upgrade", "B2")]:
        with pytest.raises(ValueError, match="afford"):
            g.apply(0, kind, cell)


def test_upgrade_only_once_and_only_own_settlements():
    g = blank_game()
    g.inventory(0).update(stone=10, wood=10)
    g.apply(0, "upgrade", "B2")
    g.apply(1, "pass", None)
    with pytest.raises(ValueError, match="already upgraded"):
        g.apply(0, "upgrade", "B2")
    with pytest.raises(ValueError, match="not one of your settlements"):
        g.apply(0, "upgrade", "C3")


def test_claim_requires_own_road():
    g = blank_game()
    with pytest.raises(ValueError):
        g.apply(0, "claim", "B3")  # empty tile
    set_tile(g, "C2", owner=1, building="road")
    with pytest.raises(ValueError):
        g.apply(0, "claim", "C2")  # opponent's road


# ---------- connectivity & blocking ------------------------------------------ #

def test_roads_only_adjacent_to_network():
    g = blank_game()
    legal_roads = {c for k, c in g.legal_actions(0) if k == "road"}
    assert legal_roads == {"A2", "B1", "B3", "C2"}
    with pytest.raises(ValueError, match="not adjacent"):
        g.apply(0, "road", "A1")  # diagonal to B2
    with pytest.raises(ValueError, match="not adjacent"):
        g.apply(0, "road", "D4")


def test_can_build_beyond_unclaimed_road_and_network_grows():
    g = blank_game()
    g.apply(0, "road", "B3")
    g.apply(1, "pass", None)
    g.apply(0, "road", "B4")  # extends from the road, before claiming it
    assert g.network(0) == {"B2", "B3", "B4"}
    g.apply(1, "pass", None)
    g.apply(0, "claim", "B3")
    assert "B4" in g.network(0)  # claiming keeps connectivity


def test_cannot_build_on_or_through_opponent_tiles():
    g = blank_game()
    set_tile(g, "B3", owner=1, building="road")
    with pytest.raises(ValueError, match="occupied"):
        g.apply(0, "road", "B3")
    with pytest.raises(ValueError, match="occupied"):
        g.apply(0, "road", "C3")  # opponent base
    # B4 is only reachable from P0 through B3 (opponent's): must be illegal
    assert ("road", "B4") not in g.legal_actions(0)


def test_legal_actions_match_validate():
    """Everything listed is accepted; everything not listed is rejected."""
    rng = random.Random(1)
    for seed in range(30):
        g = FrontierGame(seed=seed)
        while not g.s["done"]:
            pid = g.s["current_player"]
            legal = set(g.legal_actions(pid))
            for kind in ("road", "claim", "upgrade"):
                for c in CELLS:
                    assert (g.validate(pid, kind, c) is None) == ((kind, c) in legal)
            g.apply(pid, *rng.choice(sorted(legal, key=str)))


# ---------- production ------------------------------------------------------- #

def test_production_happens_after_round_and_upgrade_doubles():
    g = blank_game()
    set_tile(g, "B3", owner=0, building="settlement", resource="food", prob=1.0)
    set_tile(g, "C2", owner=1, building="settlement", upgraded=True, resource="wood", prob=1.0)
    set_tile(g, "A2", owner=0, building="road", resource="stone", prob=1.0)  # roads never produce
    g.apply(0, "pass", None)
    assert g.inventory(0)["food"] == 3  # no production mid-round
    g.apply(1, "pass", None)
    assert g.inventory(0) == {"wood": 3, "stone": 2, "food": 4}
    assert g.inventory(1) == {"wood": 5, "stone": 2, "food": 3}


def test_zero_probability_never_produces_and_bases_never_produce():
    g = blank_game()
    set_tile(g, "B3", owner=0, building="settlement", prob=0.0)
    before = {p: dict(g.inventory(p)) for p in (0, 1)}
    for _ in range(9):
        g.apply(0, "pass", None)
        g.apply(1, "pass", None)
    assert {p: g.inventory(p) for p in (0, 1)} == before


def test_tile_claimed_this_round_produces_this_round():
    g = blank_game()
    set_tile(g, "B3", owner=0, building="road", resource="food", prob=1.0)
    g.apply(0, "claim", "B3")  # food 3 -> 2
    g.apply(1, "pass", None)
    assert g.inventory(0)["food"] == 3


def test_production_rate_roughly_matches_probability():
    hits, n = 0, 0
    for seed in range(400):
        g = blank_game(seed)
        set_tile(g, "B3", owner=0, building="settlement", prob=0.3)
        g.apply(0, "pass", None)
        g.apply(1, "pass", None)
        hits += g.inventory(0)["stone"] - 2
        n += 1
    assert 0.22 < hits / n < 0.38


def test_no_production_after_final_round():
    g = blank_game()
    set_tile(g, "B3", owner=0, building="settlement", prob=1.0)
    for _ in range(9):
        g.apply(0, "pass", None)
        g.apply(1, "pass", None)
    assert g.inventory(0)["stone"] == 2 + 9
    g.apply(0, "pass", None)
    g.apply(1, "pass", None)
    assert g.s["done"] and g.inventory(0)["stone"] == 11


# ---------- scoring & winners ------------------------------------------------ #

def test_network_bonus_once_at_four_settlements():
    g = blank_game()
    for c in ("B3", "B4"):
        set_tile(g, c, owner=0, building="settlement")
    assert g.score(0) == 3
    set_tile(g, "A4", owner=0, building="settlement")
    assert g.score(0) == 4 + 2
    set_tile(g, "A3", owner=0, building="settlement")
    assert g.score(0) == 5 + 2  # bonus counted once


def finish(g):
    while not g.s["done"]:
        g.apply(g.s["current_player"], "pass", None)


def test_higher_score_wins():
    g = blank_game()
    set_tile(g, "B3", owner=0, building="settlement", prob=0.0)
    finish(g)
    assert g.outcome()[0] == 0


def test_tiebreak_settlements_then_resources_then_draw():
    # equal score (2 v 2): P0 has 2 settlements, P1 has 1 upgraded base
    g = blank_game()
    set_tile(g, "B3", owner=0, building="settlement", prob=0.0)
    g.board["C3"]["upgraded"] = True
    finish(g)
    assert g.score(0) == g.score(1) == 2
    assert g.outcome()[0] == 0 and "more settlements" in g.outcome()[1]

    g = blank_game()
    g.inventory(1)["wood"] += 1
    finish(g)
    assert g.outcome()[0] == 1 and "leftover resources" in g.outcome()[1]

    g = blank_game()
    finish(g)
    assert g.outcome()[0] is None


# ---------- TextArena env ------------------------------------------------------ #

def test_env_full_game_20_valid_turns_and_rewards():
    env = make_env(seed=3)
    done, steps = False, 0
    while not done:
        pid, obs = env.get_observation()
        done, info = env.step("[pass]")
        steps += 1
    assert steps == 20 and env.game.s["valid_turns"] == 20
    assert env.close() == {0: 0, 1: 0}  # all-pass game is a draw


def test_env_winner_rewards():
    env = make_env(seed=3)
    env.step("[road B3]")
    for _ in range(19):
        env.step("[pass]")
    # P0: B3 road only -> score tie 1 v 1, settlements tie, resources 7 v 8 -> P1 wins
    assert env.close() == {0: -1, 1: 1}


@pytest.mark.parametrize("bad", ["", "road B3", "[fly B3]", "[road E9]", "[road A1]",
                                 "[claim B3]", "[road B3] [road A2]"])
def test_invalid_move_leaves_state_unchanged_and_allows_one_retry(bad):
    env = make_env(seed=5, allowance=1)
    before = env.snapshot()
    rng_before = env.game.rng.getstate()
    done, _ = env.step(bad)
    assert not done
    assert env.snapshot() == before and env.game.rng.getstate() == rng_before
    assert env.state.current_player_id == 0
    pid, obs = env.get_observation()
    assert pid == 0 and "Your action was invalid" in obs[-1][1] and "Legal actions:" in obs[-1][1]
    done, _ = env.step(bad)  # second invalid move loses
    assert done and env.close() == {0: -1, 1: 0}


def test_invalid_move_with_spiral_allowance_zero_ends_game():
    env = make_env(seed=5, allowance=0)
    done, _ = env.step("[claim B3]")
    assert done and env.close()[0] == -1


def test_invalid_just_before_production_does_not_roll():
    env = make_env(seed=8, allowance=1)
    env.game.board["B3"].update(owner=1, building="settlement", prob=1.0, resource="stone",
                                terrain="mountain")
    env.step("[pass]")  # P0
    before = env.snapshot()
    env.step("[upgrade B2]")  # P1 does not own B2 -> invalid
    assert env.snapshot() == before
    env.step("[pass]")
    assert env.game.inventory(1)["stone"] == 3 and env.game.s["round"] == 2


def test_action_parsing_tolerates_case_and_spaces():
    assert parse_action("I will play [Road b3].")[0] == ("road", "B3")
    assert parse_action("[ claim  C 2 ]")[0] == ("claim", "C2")
    assert parse_action("[PASS]")[0] == ("pass", None)
    assert parse_action("[road B3] then again [road B3]")[0] == ("road", "B3")
    assert parse_action("[road B3] [pass]")[0] is None


def test_observation_lists_exact_legal_actions_for_spiral_parser():
    env = ta.wrappers.FirstLastObservationWrapper(make_env(seed=11))
    rng = random.Random(0)
    done = False
    while not done:
        pid, obs = env.get_observation()
        listed = parse_legal_actions(obs)
        game = env.env.game
        from frontier.env import format_action
        assert listed == [format_action(k, c) for k, c in game.legal_actions(pid)]
        assert "You are Player" in obs.split("\n")[0]  # rules prompt is always first
        done, _ = env.step(rng.choice(listed))


def test_same_seed_and_actions_replay_identically():
    def run(seed):
        env = make_env(seed=seed)
        rng = random.Random(99)
        done = False
        while not done:
            pid, _ = env.get_observation()
            done, _ = env.step(rng.choice(
                [f"[{k} {c}]" if c else "[pass]" for k, c in env.game.legal_actions(pid)]))
        return env.snapshot(), env.close()
    assert run(123) == run(123)


def test_reset_does_not_leak_state():
    env = make_env(seed=1)
    env.step("[road B3]")
    env.reset(num_players=2, seed=1)
    assert env.snapshot() == FrontierGame(seed=1).s
