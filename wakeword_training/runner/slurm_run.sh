#!/bin/bash
# One SLURM job of the training run. Resumable: a job that hits its time limit loses only the
# step in progress, and the next job with the same command carries on from the last checkpoint.
#
#   DATA=/scratch/$USER/agent_guru_wakeword_data WORK=/scratch/$USER/agent_guru_work \
#   VENV=$HOME/agent_guru_env/venv sbatch $DATA/code/slurm_run.sh [run.py options, e.g. --scale 0.01]
#
# Edit the #SBATCH lines to the cluster's partition and limits. The longest step that cannot
# be interrupted is training one model (about 10-25 min on an A100), so keep --time >= 1 hour.
#SBATCH --job-name=agent-guru-wake
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=agent-guru-wake-%j.out
set -euo pipefail
: "${DATA:?set DATA to the data folder}" "${WORK:?set WORK to the work folder}" "${VENV:?set VENV to the venv}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
"$VENV/bin/python" "$DATA/code/verify.py" --data "$DATA" --quick
"$VENV/bin/python" "$DATA/code/run.py" --data "$DATA" --work "$WORK" "$@"
