# Settings for the SOLWEIG run on Lichtenberg II. Normally you do NOT need to change anything here:
# start.sh finds your project account by itself. Edit only if start.sh asks you to.

PROJECT="${PROJECT:-}"          # Slurm account / project name (the one you use with "sbatch -A ..."). Empty = detected automatically.
PARTITION="${PARTITION:-}"      # Slurm partition. Empty = the cluster's default.
PYTHON_MODULE="${PYTHON_MODULE:-}"   # e.g. "python/3.11" - only needed if "python3" (3.9 - 3.12) is not available by default.

BLOCKS_PER_TASK="${BLOCKS_PER_TASK:-6}"   # blocks run one after the other inside one Slurm array task (one block = about 15-30 min on one core)
MAX_PARALLEL="${MAX_PARALLEL:-100}"       # at most this many array tasks at the same time (one core each)
TIME_LIMIT="${TIME_LIMIT:-08:00:00}"      # wall time per array task
MEM_PER_CPU_MB="${MEM_PER_CPU_MB:-6000}"  # memory per task (a block needs about 3 GB)
OUT_HOURS="${OUT_HOURS:-11,12,13,14,15,16}"   # local hours written as rasters (the whole day 03:00-20:00 is always computed)
