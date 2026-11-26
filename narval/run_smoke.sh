#!/bin/bash
# Short SPIRAL self-play run on Frontier Strategy. Runs INSIDE the container
# (launched by narval/job_smoke.sh), with cwd = the SPIRAL root.
#
# Flags follow SPIRAL's run.sh, adjusted to the reported baseline settings
# (4 GPUs, lr 1e-6, 128 samples per policy step, 2048-token generations).
# CHECK every line marked CHECK against the script actually submitted for
# job 7485100 before trusting this, and keep the two in sync for the full run.
set -euo pipefail

export LD_LIBRARY_PATH=$(python -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))"):${LD_LIBRARY_PATH:-}
export NCCL_CUMEM_ENABLE=0

STEPS="${STEPS:-20}"                       # policy iterations for the smoke test
BATCH=128
GPUS="${GPUS:-4}"
PER_DEVICE=$((BATCH / GPUS))
MODEL="${MODEL:-Qwen/Qwen3-4B-Base}"       # CHECK: local model path / HF cache used in the baseline
RUN_NAME="${RUN_NAME:-frontier-smoke-$(date +%Y%m%d-%H%M)}"

python train_spiral.py \
    --env_ids FrontierStrategy-v0 \
    --use_llm_obs_wrappers False \
    --eval_env_ids FrontierStrategy-v0 \
    --eval_use_llm_obs_wrappers False \
    --eval_split all \
    --gamma 1 \
    --gpus "$GPUS" \
    --gradient-checkpointing \
    --num_samples 1 \
    --rollout_batch_size "$BATCH" \
    --dump_game_state_every 1 \
    --num_envs 1 \
    --rollout_batch_size_per_device "$PER_DEVICE" \
    --pi_buffer_maxlen_per_device "$PER_DEVICE" \
    --pretrain "$MODEL" \
    --enable_prefix_caching \
    --collocate \
    --vllm_sleep \
    --vllm_gpu_ratio 0.45 \
    --rnd-seed \
    --learning_rate 0.000001 \
    --lr_scheduler constant \
    --lr_warmup_ratio 0 \
    --num_ppo_epochs 2 \
    --train_batch_size "$BATCH" \
    --train_batch_size_per_device 1 \
    --beta 0 \
    --max_model_len 12800 \
    --generate_max_length 2048 \
    --max_context_length 32768 \
    --temperature 1.0 \
    --top_p 1 \
    --eval_steps 10 \
    --save_steps -1 \
    --eval_games 16 \
    --eval_temperature 0.6 \
    --eval_top_p 0.95 \
    --eval_generate_max_length 2048 \
    --max_train $((STEPS * BATCH)) \
    --save_path "${SAVE_PATH:-$SCRATCH/oat-output}" \
    --wb-run-name "$RUN_NAME"
    # CHECK: add --use-wb / --wb_project and your math-eval flags if the baseline used them.
    # CHECK: --eval_env_ids FrontierStrategy-v0 plays the model vs SPIRAL's RandomAgent
    #        (uses the parser patched in by setup_envs.sh).
