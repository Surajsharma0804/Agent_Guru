#!/bin/bash
# Queue N copies of slurm_run.sh, each starting after the previous one ends however it ended
# (finished, failed or timed out). A finished run makes the later jobs exit in a minute, so
# over-queueing costs nothing; a timeout no longer needs anyone awake to resubmit.
#
#   DATA=... WORK=... VENV=... bash $DATA/code/submit_chain.sh 3 [run.py options]
set -euo pipefail
N="${1:?usage: submit_chain.sh <jobs> [run.py options]}"; shift
: "${DATA:?}" "${WORK:?}" "${VENV:?}"
prev=""
for i in $(seq 1 "$N"); do
  dep=${prev:+--dependency=afterany:$prev}
  prev=$(sbatch --parsable $dep --export=ALL,DATA="$DATA",WORK="$WORK",VENV="$VENV" "$DATA/code/slurm_run.sh" "$@")
  echo "queued job $i: $prev"
done
