#!/usr/bin/env bash
# Packs all results (every variant, not the test block) into ONE file to send back.   bash collect_results.sh
cd "$(dirname "$0")"
bash status.sh
dirs=$(cd results && ls -d */ 2>/dev/null | grep -v '^test/' | tr -d '/' | tr '\n' ' ')
[ -n "$dirs" ] || { echo "no results yet"; exit 1; }
tar -czf results_fortaleza_solweig.tar.gz -C results $dirs && echo "written: results_fortaleza_solweig.tar.gz ($(du -h results_fortaleza_solweig.tar.gz | cut -f1)), contains: $dirs"
echo "Send this ONE file to the thesis author (copy it off the cluster with scp, the cluster's file-transfer service or a cloud link)."
