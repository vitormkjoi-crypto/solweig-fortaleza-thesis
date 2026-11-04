#!/usr/bin/env bash
# Shows how far the run is.   bash status.sh
cd "$(dirname "$0")"
total=$(( $(wc -l < blocks.csv) - 1 ))
if [ -d results/test/done ]; then echo "test block: $(cat results/test/done/*.json 2>/dev/null | grep -o '"status": "[a-z]*"' | head -1)"; else echo "test block: not finished yet"; fi
while read -r name envs; do
  case "$name" in ""|\#*) continue;; esac
  ok=$(grep -l '"status": "ok"' results/$name/done/*.json 2>/dev/null | wc -l); empty=$(grep -l '"status": "empty"' results/$name/done/*.json 2>/dev/null | wc -l)
  failed=$(ls results/$name/failed/*.txt 2>/dev/null | wc -l)
  echo "variant $name: $ok blocks done, $empty empty (sea/outside), $failed failed, of $total"
done < variants.txt
if command -v squeue >/dev/null 2>&1; then echo "jobs: running $(squeue -u "$USER" -h -t R -n solweig 2>/dev/null | wc -l), waiting $(squeue -u "$USER" -h -t PD -n solweig 2>/dev/null | wc -l)"; fi
echo "(A variant is finished when done + empty = $total. 'failed' blocks are retried when you run  bash start.sh  again.)"
