#!/bin/bash
# Slurm job for the Frontier Strategy smoke run.
#   cd ~/frontier-strategy && bash narval/setup_envs.sh && sbatch narval/job_smoke.sh
#
# CHECK: copy --account, binds (incl. components_fixed.py) and resource lines
# from the job script used for the baseline (job 7485100).
#SBATCH --job-name=frontier-smoke
#SBATCH --account=def-CHANGEME
#SBATCH --nodes=1
#SBATCH --gpus-per-node=a100:4
#SBATCH --cpus-per-task=32
#SBATCH --mem=400G
#SBATCH --time=04:00:00
#SBATCH --output=%x-%j.out
set -euo pipefail

module load apptainer/1.4.5

REPO="${SLURM_SUBMIT_DIR:-$(pwd)}"         # submit from the repo root
SIF="${SIF:-$SCRATCH/spiral_v1.sif}"       # CHECK image name
SPIRAL_ROOT="${SPIRAL_ROOT:-/opt/spiral}"
EXTRA_BINDS="${EXTRA_BINDS:-}"             # e.g. "--bind $SCRATCH/components_fixed.py:/opt/spiral/spiral/components.py"  CHECK

[ -f "$REPO/narval/run_smoke.sh" ] || { echo "Submit from the frontier-strategy repo root"; exit 1; }
grep -q FrontierStrategy-v0 "$SCRATCH/spiral_agents/utils.py" || { echo "Run narval/setup_envs.sh first"; exit 1; }

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # compute nodes have no internet

echo "Job $SLURM_JOB_ID on $(hostname) at $(date)"
nvidia-smi --query-gpu=name,memory.total --format=csv

# shellcheck disable=SC2086
apptainer exec --nv \
  --bind "$SCRATCH/spiral_envs:$SPIRAL_ROOT/spiral/envs" \
  --bind "$SCRATCH/spiral_agents:$SPIRAL_ROOT/spiral/agents" \
  --bind "$REPO:$REPO" \
  --bind "$SCRATCH:$SCRATCH" \
  $EXTRA_BINDS \
  --pwd "$SPIRAL_ROOT" \
  "$SIF" bash "$REPO/narval/run_smoke.sh"

echo "Finished at $(date)"
