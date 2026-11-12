#!/usr/bin/env bash
# One command to run everything:   bash start.sh
#   1. finds your Slurm project account (asks only if you have several),
#   2. creates the Python environment (once),
#   3. submits ONE test block; only if it succeeds do the real runs start by themselves:
#      every model variant listed in variants.txt, one after the other, each over all 1,379 blocks of the city.
# Safe to run again (finished blocks are skipped).   Run a single variant only:  bash start.sh base
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh
ONLY="${1:-all}"
mkdir -p logs results

# --- 1. account
if [ -z "$PROJECT" ]; then
  if command -v sacctmgr >/dev/null 2>&1; then
    mapfile -t ACC < <(sacctmgr -n -P show assoc user="$USER" format=account 2>/dev/null | sort -u | grep -v '^$' || true)
    if [ "${#ACC[@]}" -eq 1 ]; then PROJECT="${ACC[0]}"; echo "[start] using Slurm account: $PROJECT"
    else
      echo "[start] Your Slurm accounts: ${ACC[*]:-none found}"
      echo "[start] Open config.sh, put the right one in PROJECT=\"...\" and run  bash start.sh  again."; exit 1
    fi
  else
    echo "[start] sacctmgr not available. Open config.sh, put your project name in PROJECT=\"...\" and run  bash start.sh  again."; exit 1
  fi
fi

# --- 2. environment and inputs
bash setup_env.sh
n_in=$(ls inputs/CDSM/*.tif 2>/dev/null | wc -l || true)
if [ "$n_in" -lt 300 ]; then
  echo "[start] The input tiles are missing (found $n_in, expected about 451): unzip solweig_hpc_inputs.zip into this folder so that inputs/DEM, inputs/DSM and inputs/CDSM exist."; exit 1
fi

n_lc=$(ls inputs/LC/*.tif 2>/dev/null | wc -l || true)
if [ "$n_lc" -lt 300 ]; then
  echo "[start] The land-cover tiles are missing (found $n_lc, expected about 451): unzip solweig_hpc_landcover.zip into this folder so that inputs/LC exists."; exit 1
fi

COMMON=(-A "$PROJECT" --mem-per-cpu="$MEM_PER_CPU_MB")
if [ -n "$PARTITION" ]; then COMMON+=(-p "$PARTITION"); fi
NB=$(( $(wc -l < blocks.csv) - 1 ))
NT=$(( (NB + BLOCKS_PER_TASK - 1) / BLOCKS_PER_TASK ))

# --- 3. test block, then the variants one after the other
TID=$(sbatch --parsable "${COMMON[@]}" -t 01:30:00 --array=1-1 \
      --export=ALL,BLOCKS_FILE=blocks_test.csv,VARIANT=test,BLOCKS_PER_TASK=1,OUT_HOURS="$OUT_HOURS" job_array.sbatch)
TID="${TID%%;*}"
echo "[start] test block submitted: job $TID"
prev="$TID"; deptype="afterok"; n=0
while read -r name envs; do
  case "$name" in ""|\#*) continue;; esac
  if [ "$ONLY" != "all" ] && [ "$ONLY" != "$name" ]; then continue; fi
  EXP="ALL,BLOCKS_FILE=blocks.csv,VARIANT=${name},BLOCKS_PER_TASK=${BLOCKS_PER_TASK},OUT_HOURS=${OUT_HOURS}"
  for kv in $envs; do EXP="${EXP},${kv}"; done
  id=$(sbatch --parsable "${COMMON[@]}" -t "$TIME_LIMIT" --array="1-${NT}%${MAX_PARALLEL}" \
       --dependency="${deptype}:${prev}" --kill-on-invalid-dep=yes --export="$EXP" job_array.sbatch)
  id="${id%%;*}"; echo "[start] variant '${name}' submitted: job $id (starts after job $prev)"
  prev="$id"; deptype="afterany"; n=$((n + 1))
done < variants.txt
if [ "$n" -eq 0 ]; then echo "[start] No variant named '$ONLY' in variants.txt"; exit 1; fi
echo "[start] Done submitting $n variant(s). Check progress with:  bash status.sh      Logs are in logs/"
