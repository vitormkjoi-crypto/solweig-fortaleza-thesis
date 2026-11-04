#!/usr/bin/env bash
# Slurm array job: task N runs blocks (N-1)*BLOCKS_PER_TASK+1 ... N*BLOCKS_PER_TASK of the block list in $BLOCKS_FILE.
# Submitted by start.sh (account, partition, time, memory, array range are given on the sbatch command line). Do not run by hand.
#SBATCH --job-name=solweig
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/%x_%A_%a.out
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")}"
source ./config.sh
if [ -n "${PYTHON_MODULE}" ]; then
  if ! type module >/dev/null 2>&1; then for f in /etc/profile.d/lmod.sh /etc/profile.d/modules.sh /usr/share/lmod/lmod/init/bash; do if [ -f "$f" ]; then source "$f"; break; fi; done; fi
  module load ${PYTHON_MODULE}
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
export VARIANT="${VARIANT:-base}" WEATHER="${WEATHER:-clearsky}" OUT_HOURS="${OUT_HOURS}"
BLOCKS_FILE="${BLOCKS_FILE:-blocks.csv}"
first=$(( (SLURM_ARRAY_TASK_ID - 1) * BLOCKS_PER_TASK + 1 ))
echo "task ${SLURM_ARRAY_TASK_ID}: blocks ${first}..$((first + BLOCKS_PER_TASK - 1)) of ${BLOCKS_FILE}, variant ${VARIANT}, weather ${WEATHER}, host $(hostname), $(date)"
./venv/bin/python -m solweig_hpc.run_block --blocks "${BLOCKS_FILE}" --inputs inputs --out results --index "${first}" --count "${BLOCKS_PER_TASK}"
echo "task ${SLURM_ARRAY_TASK_ID} finished $(date)"
