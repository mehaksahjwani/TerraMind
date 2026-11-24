#!/bin/bash
# Copy SPIRAL's envs/ and agents/ folders out of the container into $SCRATCH, add
# Frontier Strategy, and register it. The image itself is never modified; the
# patched folders are bind-mounted over the originals at run time.
#
# Two patches are needed (the second is easy to miss):
#   1. spiral/envs/__init__.py        -> register FrontierStrategy-v0
#   2. spiral/agents/utils.py         -> add its valid-action parser. SPIRAL's
#      train loop calls get_valid_action_parser(env_id) every turn and raises
#      NotImplementedError for envs without one.
#
# Safe to re-run: it refreshes env.py and only appends each patch once.
#
# Usage:  bash narval/setup_envs.sh            (SIF=/path/to/image.sif to override)
set -euo pipefail

module load apptainer/1.4.5

REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
SIF="${SIF:-$SCRATCH/spiral_v1.sif}"          # CHECK: handoff also mentions spiral_mehak_v1.sif
SPIRAL_IN_IMAGE="${SPIRAL_IN_IMAGE:-/opt/spiral/spiral}"
ENVS_DIR="$SCRATCH/spiral_envs"
AGENTS_DIR="$SCRATCH/spiral_agents"

[ -f "$SIF" ] || { echo "SIF not found: $SIF (set SIF=...)"; exit 1; }

# 1. copy SPIRAL's folders out of the container (once)
[ -d "$ENVS_DIR" ]   || apptainer exec "$SIF" cp -r "$SPIRAL_IN_IMAGE/envs"   "$ENVS_DIR"
[ -d "$AGENTS_DIR" ] || apptainer exec "$SIF" cp -r "$SPIRAL_IN_IMAGE/agents" "$AGENTS_DIR"

# 2. add our game (always refresh env.py from the repo)
mkdir -p "$ENVS_DIR/FrontierStrategy"
cp "$REPO/frontier/env.py" "$ENVS_DIR/FrontierStrategy/env.py"
touch "$ENVS_DIR/FrontierStrategy/__init__.py"

# 3. register it (same pattern as PigDice)
if ! grep -q 'FrontierStrategy-v0' "$ENVS_DIR/__init__.py"; then
cat >> "$ENVS_DIR/__init__.py" <<'EOF'

# Frontier Strategy (two-player) - added by frontier-strategy/narval/setup_envs.sh
register(
    id="FrontierStrategy-v0",
    entry_point="spiral.envs.FrontierStrategy.env:FrontierStrategyEnv",
)
EOF
fi

# 4. register its valid-action parser (also used by SPIRAL's RandomAgent for eval)
if ! grep -q 'FrontierStrategy-v0' "$AGENTS_DIR/utils.py"; then
cat >> "$AGENTS_DIR/utils.py" <<'EOF'


# Frontier Strategy - added by frontier-strategy/narval/setup_envs.sh
from spiral.envs.FrontierStrategy.env import parse_legal_actions as _frontier_parse_legal_actions

_VALID_ACTION_PARSER["FrontierStrategy-v0"] = _frontier_parse_legal_actions
EOF
fi

echo "Patched folders ready:"
echo "  $ENVS_DIR   -> bind to $SPIRAL_IN_IMAGE/envs"
echo "  $AGENTS_DIR -> bind to $SPIRAL_IN_IMAGE/agents"
echo
echo "Check (runs inside the container):  bash $REPO/narval/check_env.sh"
