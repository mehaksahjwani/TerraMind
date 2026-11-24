"""Local registration of Frontier Strategy for TextArena.

On Narval the game is registered by SPIRAL's ``spiral/envs/__init__.py`` instead
(see narval/setup_envs.sh); this module is only for local play and tests.
"""

import textarena as ta
from textarena.envs.registration import ENV_REGISTRY

from frontier.env import FrontierGame, FrontierStrategyEnv, parse_action, parse_legal_actions

ENV_ID = "FrontierStrategy-v0"

if ENV_ID not in ENV_REGISTRY:
    ta.register(id=ENV_ID, entry_point="frontier.env:FrontierStrategyEnv")

__all__ = ["ENV_ID", "FrontierGame", "FrontierStrategyEnv", "parse_action", "parse_legal_actions"]
