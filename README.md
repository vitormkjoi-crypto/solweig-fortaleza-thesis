# SOLWEIG run for Fortaleza (Lichtenberg II)

Simulates hourly mean radiant temperature (Tmrt, 1.1 m above ground, 1 m grid) for the whole city of Fortaleza, Brazil, on 2025-11-12,
with the SOLWEIG model (UMEP code), for a Master's thesis (TU Darmstadt, Sustainable Urban Development) on heat exposure of public-transport riders.
The city is cut into 1,379 blocks of 500 m; each block is an independent one-core job. The whole city is run several times with different model
settings ("variants", listed in `variants.txt`) so that the thesis can compare them.

## What you have to do (about 10 minutes, three commands)

You do not need to understand the model. Everything runs by itself once started.

**A. Get the files onto the cluster.** There are two ways; use whichever is easier.

*Way 1 - from GitHub (this repository).* On the cluster, in your work or scratch directory (not your small home directory: the folder grows to a few GB):

```
git clone <the address of this repository>
cd <the repository folder>
```

then download the two input files from this repository's **Releases** page (right-click each file -> copy link address; the files are `solweig_hpc_inputs.zip`, 0.7 GB, and `solweig_hpc_landcover.zip`, a few MB):

```
wget "<copied link of solweig_hpc_inputs.zip>" -O solweig_hpc_inputs.zip
wget "<copied link of solweig_hpc_landcover.zip>" -O solweig_hpc_landcover.zip
unzip solweig_hpc_inputs.zip
unzip solweig_hpc_landcover.zip
```

(If the cluster has no internet, download the files in your browser and copy them over with scp or the file-transfer service.)

*Way 2 - from zip files.* If you received `solweig_hpc_code.zip`, `solweig_hpc_inputs.zip` and `solweig_hpc_landcover.zip` instead:

```
mkdir solweig_fortaleza && cd solweig_fortaleza
unzip ../solweig_hpc_code.zip
unzip ../solweig_hpc_inputs.zip
unzip ../solweig_hpc_landcover.zip
```

In both ways you should now see `start.sh`, `blocks.csv`, `variants.txt` and the folder `inputs/` (with the sub-folders `DEM`, `DSM`, `CDSM` and `LC`) next to each other.
If the next step complains that `pip` has no internet, also download `solweig_hpc_wheelhouse.zip` (Releases page) and unzip it in the same folder.
**B. Start it.**

```
bash start.sh
```

What this does, in order: finds your Slurm project account (if you have several it tells you to write the right one into `config.sh`),
builds a small Python environment (a minute or two), submits ONE test block, and submits all the real runs so that they only
start after the test succeeded. It then prints the job numbers and returns. You can log out; the jobs keep running on the cluster.
If something is wrong it stops and prints one line saying what to do.

**C. When it is finished, send back one file.** Check any time with `bash status.sh` (a variant is finished when "done + empty" equals the
total). When all variants are finished (expect from a few hours to about a day, depending on the queue), run

```
bash collect_results.sh
```

and send the file `results_fortaleza_solweig.tar.gz` (about 5-8 GB) to the thesis author.

**If something goes wrong:** run `bash status.sh`, then send the thesis author the output of `bash status.sh` and the last 30 lines of the newest
file in `logs/` (for example `tail -n 30 $(ls -t logs/* | head -1)`). Running `bash start.sh` again is always safe: finished blocks are skipped
and failed ones are retried.

## What it uses on the cluster

* About 430 core-hours per variant (one block took 19 minutes on one laptop core; cluster cores may differ). With the 7 variants of
  `variants.txt` that is about 3,000 core-hours in total, running at most 100 one-core tasks at a time (setting in `config.sh`).
  To run fewer variants, delete lines from `variants.txt` before starting (keep the line `base`), or run only one with `bash start.sh base`.
* About 3 GB of memory per task (6 GB are requested), one core per task, 8 hours maximum per array task.
* About 10 GB of disk in total (inputs 1 GB, results about 1 GB per variant).
* Please check that your project's description covers this kind of work (non-commercial research); if in doubt, ask the HRZ.

## Files

* `start.sh`, `status.sh`, `collect_results.sh`, `setup_env.sh`, `job_array.sbatch`, `config.sh` - the workflow; `variants.txt` - the model runs.
* `blocks.csv` (all blocks), `blocks_test.csv` (the one test block).
* `landcover/landcoverclasses_2016a.txt` - UMEP's table of surface properties per land-cover class (UMEP-dev team, GPL-3).
* `weather/` - NASA POWER hourly weather for 2025-11-12 (local time = UTC-3) in UMEP's format.
* `solweig_hpc/run_block.py` - the program; `solweig_hpc/umep_core/` - SOLWEIG, sky-view-factor and wall-height code copied from the
  UMEP QGIS plugin (UMEP-dev team, GPL-3, https://github.com/UMEP-dev/UMEP) with only three small edits (see
  `umep_core/README_umep_core.txt`), so it runs without QGIS.
* `results/<variant>/` (created): `tmrt_hHH/` (Tmrt in 0.01 degC, int16), `shadow_hHH/` (shade 0-100 %, uint8) for the hours 11-16 local time,
  `done/*.json` (timings and statistics per block), `failed/` (error texts, if any).

## Model settings (UMEP defaults unless stated; the variants change one setting each)

Standing person (1.1 m), shortwave absorption 0.70, longwave 0.95, wall albedo 0.20 / emissivity 0.90, isotropic sky, diffuse and direct
shortwave estimated from clear-sky global radiation (NASA POWER, as in Shaver et al. 2026), trees evergreen with 3 % shortwave
transmissivity and a trunk zone of 25 % of canopy height, wall limit 3 m.
Land cover (UMEP scheme; Shaver et al. 2026 also use land cover): water (lakes, rivers, wetlands, pools), grass (all vegetation polygons),
buildings (surface 2 m or more above ground) and all other ground = UMEP dark asphalt; albedo, emissivity and surface-heating values per class are
UMEP's own table (`landcover/landcoverclasses_2016a.txt`). The variant `ground_default` gives the other ground the plain default surface (albedo 0.15) instead.
Inputs: city LiDAR 2023 (Prefeitura de Fortaleza, SEFIN, IDE-SEFIN, CC BY 4.0) averaged to 1 m, building footprints, vegetation
and water polygons from the same portal (`inputs/LC` = land-cover tiles, codes 0 other ground, 5 grass, 7 water).

## References

Lindberg, F., Holmer, B., Thorsson, S. (2008). SOLWEIG 1.0. Int. J. Biometeorology 52, 697-713.
Lindberg, F. et al. (2018). UMEP. Environmental Modelling & Software 99, 70-87.
Shaver, H. et al. (2026). Transportation Research Part D 157, 105398.
