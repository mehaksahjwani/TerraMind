#!/bin/bash
# Load FrontierStrategy-v0 inside the container exactly as SPIRAL will, play one
# full random game through SPIRAL's own RandomAgent (which uses the patched
# parser), and print which spiral package Python actually imported.
set -euo pipefail

module load apptainer/1.4.5

SIF="${SIF:-$SCRATCH/spiral_v1.sif}"
SPIRAL_ROOT="${SPIRAL_ROOT:-/opt/spiral}"

apptainer exec \
  --bind "$SCRATCH/spiral_envs:$SPIRAL_ROOT/spiral/envs" \
  --bind "$SCRATCH/spiral_agents:$SPIRAL_ROOT/spiral/agents" \
  --pwd "$SPIRAL_ROOT" "$SIF" \
  python - <<'EOF'
import spiral, spiral.envs, textarena as ta
from spiral.envs import make_env
from spiral.agents.random import RandomAgent
from spiral.agents.utils import get_valid_action_parser

print("spiral imported from:", spiral.__file__)
print("textarena version:", getattr(ta, "__version__", "unknown"))

env = make_env("FrontierStrategy-v0", use_llm_obs_wrapper=False)
env.reset(num_players=2, seed=0)
env.state.error_allowance = 0          # what SPIRAL training does
pid, obs = env.get_observation()
print(obs[:1500])
print("parsed legal actions:", get_valid_action_parser("FrontierStrategy-v0")(obs))

agent, done, n = RandomAgent("FrontierStrategy-v0"), False, 0
while not done:
    pid, obs = env.get_observation()
    done, info = env.step(agent(obs))
    n += 1
print(f"random game finished after {n} actions; rewards={env.close()}; {info.get('reason')}")
assert n == 20, "expected exactly 20 valid actions"
print("OK")
EOF
