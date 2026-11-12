#!/usr/bin/env python3
"""Run SOLWEIG (UMEP code, CPU, no QGIS needed) for one or several 500 m blocks of Fortaleza.

For every block: read 1 m DEM / buildings-only DSM / canopy CDSM (block + margin) from the input tiles, compute wall height and aspect,
sky view factors (with vegetation) and hourly SOLWEIG Tmrt at 1.1 m for 2025-11-12, then write the block core (margin cut off) as
compressed GeoTIFF for the requested hours (Tmrt in 0.01 C as int16, shade as 0-100 % uint8).

    python -m solweig_hpc.run_block --blocks blocks.csv --inputs inputs --out results --index 12 --count 8

Settings are UMEP defaults, same as in the thesis test runs (see README.md). Land cover (water, grass, buildings, other ground; tiles in inputs/LC) is used unless LANDCOVER=off. Variants for sensitivity runs via environment variables: VARIANT (name of the output sub-folder), WEATHER (clearsky|allsky),
GROUND (paved|default: what "other ground" is), LANDCOVER (on|off), ALB_G, EMIS_G (other ground), ALB_B (walls and roofs), EMIS_W, TRANS, OUT_HOURS (e.g. "11,12,13,14,15,16").
"""
import os, sys, json, time, argparse, csv, gc
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from solweig_hpc.umep_core.SkyViewFactorCalculator.svfworker import Worker as SvfWorker
from solweig_hpc.umep_core.WallHeight.wallworker import Worker as WallWorker
from solweig_hpc.umep_core.WallHeight import wallalgorithms as wa
from solweig_hpc.umep_core.SOLWEIG.solweigworker import Worker as SolWorker
from solweig_hpc.umep_core.Utilities.SEBESOLWEIGCommonFiles.Solweig_v2015_metdata_noload import Solweig_2015a_metdata_noload

X0, Y0, TILE = 539123.2103, 9592228.4996, 1000      # global 1 m grid (same as the LiDAR download); tile i, j = column, row of 1 km tiles
NODATA = -32768


class Dummy:
    """Stands in for UMEP's dialog: progress bars do nothing, the check boxes named in `on` are ticked."""
    def __init__(self, on=()):
        self.on = on
    def __getattr__(self, n):
        class W:
            def __init__(s, on): s.on = on
            def isChecked(s): return n in s.on
            def __call__(s, *a, **k): return None
            def __getattr__(s, m): return lambda *a, **k: None
        return W(self.on)


def read_window(rio, folder, prefix, c0, r0, nc, nr, raw=False):
    """Read a window of the global 1 m grid (column c0, row r0, size nc x nr) from the 1 km tiles; missing tiles give NaN.
    Height tiles are int16 centimetres (NoData -32768) and are returned in metres; raw=True returns the stored values unchanged (land-cover codes)."""
    out = np.full((nr, nc), np.nan)
    for tj in range(max(r0, 0) // TILE, (r0 + nr - 1) // TILE + 1):
        for ti in range(max(c0, 0) // TILE, (c0 + nc - 1) // TILE + 1):
            f = os.path.join(folder, "%s_i%02d_j%02d.tif" % (prefix, ti, tj))
            if not os.path.exists(f):
                continue
            with rio.open(f) as ds:
                a = ds.read(1).astype(float)
            if not raw:
                a[a == NODATA] = np.nan
                a /= 100.0
            ya0, xa0 = tj * TILE, ti * TILE
            ys, ye = max(r0, ya0), min(r0 + nr, ya0 + a.shape[0]); xs, xe = max(c0, xa0), min(c0 + nc, xa0 + a.shape[1])
            if ye > ys and xe > xs:
                out[ys - r0:ye - r0, xs - c0:xe - c0] = a[ys - ya0:ye - ya0, xs - xa0:xe - xa0]
    return out


def run_one(blk, args, rio, T):
    from rasterio.transform import from_origin
    from rasterio.warp import transform as rio_transform
    from scipy import ndimage
    bid = blk["block_id"]; size = int(blk["size"]); m = args.margin
    c0, r0 = int(blk["c0"]), int(blk["r0"]); nc = nr = size + 2 * m
    done_dir = os.path.join(args.out, args.variant, "done"); os.makedirs(done_dir, exist_ok=True)
    done = os.path.join(done_dir, bid + ".json")
    if os.path.exists(done):
        print(bid, "already done, skipped", flush=True); return
    t0 = time.time(); lap = {}
    def tick(name):
        nonlocal t0
        lap[name] = round(time.time() - t0, 1); print("  [%7.1f s] %s" % (lap[name], name), flush=True); t0 = time.time()
    wc0, wr0 = c0 - m, r0 - m
    dem = read_window(rio, os.path.join(args.inputs, "DEM"), "dem", wc0, wr0, nc, nr)
    dsm = read_window(rio, os.path.join(args.inputs, "DSM"), "dsm", wc0, wr0, nc, nr)
    cdsm = read_window(rio, os.path.join(args.inputs, "CDSM"), "cdsm", wc0, wr0, nc, nr)
    valid = np.isfinite(dem)
    core_valid = valid[m:m + size, m:m + size].mean()
    if core_valid < 0.01:
        json.dump({"block": bid, "status": "empty", "core_valid_share": float(core_valid)}, open(done, "w")); print(bid, "no data, skipped", flush=True); return
    if not valid.all():                              # fill gaps (outside the survey / sea) with the nearest ground height
        idx = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
        dem = dem[tuple(idx)]
    dsm = np.where(np.isfinite(dsm), dsm, dem); cdsm = np.where(np.isfinite(cdsm), cdsm, 0.0)
    dsm = np.maximum(dsm, 0.0) if dsm.min() < -50 else dsm
    raise_ = abs(min(dsm.min(), dem.min())) if min(dsm.min(), dem.min()) < 0 else 0.0   # same raise for both, keeps heights above ground
    dsm = dsm + raise_; dem = dem + raise_
    rows, cols = dsm.shape; scale = 1.0
    tick("inputs")

    walls = wa.findwalls(dsm, 3.0); holder = {}
    w = WallWorker(walls.copy(), scale, dsm, Dummy()); w.finished.connect(lambda r: holder.update(wall=r)); w.error.connect(lambda e: holder.update(err=e)); w.run()
    if "wall" not in holder: raise RuntimeError("wall worker failed: %s" % holder.get("err"))
    wallheight = walls; wallaspect = holder["wall"]["dirwalls"]; tick("walls")

    trans = float(os.environ.get("TRANS", "0.03")); trunkratio = 0.25
    sv = SvfWorker(dsm.copy(), cdsm.copy(), cdsm * trunkratio, scale, 1, Dummy()); sv.finished.connect(lambda r: holder.update(svf=r)); sv.error.connect(lambda e: holder.update(err=e)); sv.run()
    if "svf" not in holder: raise RuntimeError("svf worker failed: %s" % holder.get("err"))
    S = holder["svf"]; tick("svf")
    svf, svfN, svfW, svfE, svfS = S["svf"], S["svfN"], S["svfW"], S["svfE"], S["svfS"]
    svfveg, svfNveg, svfEveg, svfSveg, svfWveg = S["svfveg"], S["svfNveg"], S["svfEveg"], S["svfSveg"], S["svfWveg"]
    svfaveg, svfNaveg, svfEaveg, svfSaveg, svfWaveg = S["svfaveg"], S["svfNaveg"], S["svfEaveg"], S["svfSaveg"], S["svfWaveg"]
    del S, holder["svf"]; gc.collect()

    met = np.loadtxt(os.path.join(ROOT, "weather", "metdata_%s.txt" % os.environ.get("WEATHER", "clearsky")), skiprows=1, delimiter=" ")
    x_sw = X0 + wc0; y_sw = Y0 - (wr0 + nr)
    lon, lat = [v[0] for v in rio_transform("EPSG:31984", "EPSG:4326", [x_sw], [y_sw])]
    if os.environ.get("FORCE_LONLAT"):               # testing only: reproduce a run made at another position
        lon, lat = [float(v) for v in os.environ["FORCE_LONLAT"].split(",")]
    location = {"longitude": lon, "latitude": lat, "altitude": 3.0}; UTC = -3
    YYYY, altitude, azimuth, zen, jday, leafon, dectime, altmax = Solweig_2015a_metdata_noload(met, location, UTC)
    n = met.shape[0]; DOY = met[:, 1]; hours = met[:, 2]; minu = met[:, 3]
    Ta = met[:, 11]; RH = met[:, 10]; radG = met[:, 14]; radD = met[:, 21]; radI = met[:, 22]; P = met[:, 12]; Ws = met[:, 9]
    absK, absL = 0.70, 0.95
    albedo_b = float(os.environ.get("ALB_B", "0.20")); ewall = float(os.environ.get("EMIS_W", "0.90"))
    albedo_g = float(os.environ.get("ALB_G", "0.15")); eground = float(os.environ.get("EMIS_G", "0.95"))
    Fside, Fup, height, Fcyl = 0.22, 0.06, 1.1, 0.28; cyl = 1; elvis = 0; onlyglobal = 1
    Knight = np.zeros((rows, cols))
    buildings = dsm - dem; buildings[buildings < 2.] = 1.; buildings[buildings >= 2.] = 0.
    leafon = np.ones((1, n)); psi = leafon * trans
    vegmax = cdsm.max(); amaxvalue = max(dsm.max() - dsm.min(), vegmax)
    vegdsm = cdsm + dsm; vegdsm[vegdsm == dsm] = 0; vegdsm2 = cdsm * trunkratio + dsm; vegdsm2[vegdsm2 == dsm] = 0
    bush = np.logical_not(vegdsm2 * vegdsm) * vegdsm
    svfbuveg = svf - (1. - svfveg) * (1. - trans)
    tmp = svf + svfveg - 1.; tmp[tmp < 0.] = 0.; svfalfa = np.arcsin(np.exp(np.log(1. - tmp) / 2.))
    first = np.round(height); second = np.round(height * 20.)
    TgK = Knight + 0.37; Tstart = Knight - 3.41; alb_grid = Knight + albedo_g; emis_grid = Knight + eground
    timestepdec = dectime[1] - dectime[0]

    # ---- land cover (UMEP scheme), as in Shaver et al. (2026) who name land cover as an input of their microclimate model ----
    # Tiles inputs/LC (codes 0 other ground, 5 grass, 7 water) + buildings (code 2: DSM - DEM >= 2 m). Surface properties per class from UMEP's own table
    # (landcover/landcoverclasses_2016a.txt). GROUND=paved: "other ground" = UMEP dark asphalt (class 1); GROUND=default: the plain default surface (as the runs without land cover).
    # LANDCOVER=off: old behaviour, one default surface for all ground. ALB_G / EMIS_G change the "other ground" class, ALB_B the walls and roofs.
    lc_dir = os.path.join(args.inputs, "LC"); use_lc = os.environ.get("LANDCOVER", "on") != "off"
    if use_lc and not os.path.isdir(lc_dir):
        raise RuntimeError("land-cover tiles missing: unzip solweig_hpc_landcover.zip so that inputs/LC exists (or set LANDCOVER=off for a run without land cover)")
    ground = os.environ.get("GROUND", "paved"); landcover = 0; lcgrid = 0; TmaxLST = 15.; TmaxLST_wall = 15.; TgK_wall = 0.37; Tstart_wall = -3.41; lc_counts = {}
    if use_lc:
        from solweig_hpc.umep_core.SOLWEIG.SOLWEIGpython.Tgmaps_v1 import Tgmaps_v1
        lc = np.nan_to_num(read_window(rio, lc_dir, "lc", wc0, wr0, nc, nr, raw=True), nan=0.0)
        other = 1 if ground == "paved" else 0
        lc[lc == 0] = other
        lcgrid = lc.copy(); lcgrid[buildings == 0] = 2
        lines = open(os.path.join(ROOT, "landcover", "landcoverclasses_2016a.txt")).readlines()[1:]
        lc_class = np.array([[float(v) for v in l.split()[1:7]] for l in lines if l.strip()])     # columns: code, albedo, emissivity, Ts_deg, Tstart, TmaxLST
        if ground != "paved":
            lc_class[lc_class[:, 0] == 0, :] = [0, 0.15, 0.95, 0.37, -3.41, 15.0]              # default surface = the ground of the runs without land cover
        if "ALB_G" in os.environ: lc_class[lc_class[:, 0] == other, 1] = albedo_g              # sensitivity variants: only when set
        if "EMIS_G" in os.environ: lc_class[lc_class[:, 0] == other, 2] = eground
        if "ALB_B" in os.environ: lc_class[lc_class[:, 0] == 2, 1] = albedo_b                  # roofs (walls use albedo_b directly)
        TgK, Tstart, alb_grid, emis_grid, TgK_wall, Tstart_wall, TmaxLST, TmaxLST_wall = Tgmaps_v1(lcgrid, lc_class)
        TgK_wall = float(np.ravel(TgK_wall)[0]); Tstart_wall = float(np.ravel(Tstart_wall)[0]); TmaxLST_wall = float(np.ravel(TmaxLST_wall)[0])
        landcover = 1; lc_counts = {int(k): int(v) for k, v in zip(*np.unique(lcgrid[m:m + size, m:m + size], return_counts=True))}
        print("  land cover (core): %s, other ground = %s" % (lc_counts, ground), flush=True)

    wanted = [int(h) for h in os.environ.get("OUT_HOURS", args.hours).split(",")]
    store = {}
    class Writer:
        def write(self, filename, arr):
            base = os.path.basename(filename); kind = base.split("_")[0]; hh = int(base.split("_")[-1][:2])
            if kind in ("Tmrt", "Shadow") and hh in wanted:
                store[(kind, hh)] = np.array(arr[m:m + size, m:m + size])
    tick("setup")
    argv = (dsm, scale, rows, cols, svf, svfN, svfW, svfE, svfS, svfveg, svfNveg, svfEveg, svfSveg, svfWveg, svfaveg, svfEaveg, svfSaveg, svfWaveg, svfNaveg,
            vegdsm, vegdsm2, albedo_b, absK, absL, ewall, Fside, Fup, Fcyl, altitude, azimuth, zen, jday, 1, onlyglobal, buildings, location,
            psi, landcover, lcgrid, dectime, altmax, wallaspect, wallheight, cyl, elvis, Ta, RH, radG, radD, radI, P, amaxvalue,
            bush, [], TgK, Tstart, alb_grid, emis_grid, TgK_wall, Tstart_wall, TmaxLST, TmaxLST_wall, first, second, svfalfa, svfbuveg, 1., 0., 0., 0., 0., 0., timestepdec,
            Knight.copy(), Knight.copy(), Knight.copy(), Knight.copy(), Knight.copy(), 1., Dummy(on=("CheckBoxTmrt", "CheckBoxShadow")),
            YYYY, DOY, hours, minu, Writer(), ["."], None, None, Ws, 75., 35., 1.75, 80., 0.9, 1, 10.,
            None, None, None, None, 0, None, 0)
    sw = SolWorker(*argv); sw.finished.connect(lambda r: holder.update(sol=r)); sw.error.connect(lambda e: holder.update(err=e)); sw.run()
    if "sol" not in holder or holder["sol"] is None: raise RuntimeError("SOLWEIG failed: %s" % holder.get("err"))
    tick("solweig")

    transform = from_origin(X0 + c0, Y0 - r0, 1, 1)
    prof = dict(driver="GTiff", height=size, width=size, count=1, crs="EPSG:31984", transform=transform, compress="deflate", predictor=2, tiled=True, blockxsize=256, blockysize=256)
    stats = {}
    for (kind, hh), arr in sorted(store.items()):
        d = os.path.join(args.out, args.variant, "%s_h%02d" % (kind.lower(), hh)); os.makedirs(d, exist_ok=True)
        if kind == "Tmrt":
            a = np.where(np.isfinite(arr), np.round(arr * 100), NODATA).clip(-32767, 32767).astype("int16"); nodata = NODATA; dtype = "int16"
            stats["tmrt_median_h%02d" % hh] = float(np.nanmedian(arr)); stats["tmrt_share_ge65_h%02d" % hh] = float(np.mean(arr >= 65.0))
        else:
            a = np.round(np.clip(arr, 0, 1) * 100).astype("uint8"); nodata = 255; dtype = "uint8"
            stats["sunlit_share_h%02d" % hh] = float(np.mean(arr > 0.5))
        with rio.open(os.path.join(d, "%s_%s.tif" % (kind.lower(), bid)), "w", dtype=dtype, nodata=nodata, **prof) as ds:
            ds.write(a, 1)
    tick("write")
    json.dump({"block": bid, "status": "ok", "size": size, "margin": m, "variant": args.variant, "seconds": lap, "stats": stats, "raise_m": raise_, "land_cover": bool(landcover), "other_ground": ground if landcover else None, "land_cover_core_cells": lc_counts,
               "lon": lon, "lat": lat, "host": os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "")}, open(done, "w"), indent=1)
    print(bid, "done:", json.dumps(lap), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", default=os.path.join(ROOT, "blocks.csv")); ap.add_argument("--inputs", default=os.path.join(ROOT, "inputs"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results")); ap.add_argument("--margin", type=int, default=100)
    ap.add_argument("--index", type=int, default=1, help="first block (1-based row of blocks.csv)"); ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--block-id", default=None); ap.add_argument("--hours", default="11,12,13,14,15,16")
    ap.add_argument("--variant", default=os.environ.get("VARIANT", "base"))
    args = ap.parse_args()
    import rasterio
    rows = list(csv.DictReader(open(args.blocks)))
    sel = [r for r in rows if r["block_id"] == args.block_id] if args.block_id else rows[args.index - 1:args.index - 1 + args.count]
    print("blocks to do:", [r["block_id"] for r in sel], "variant", args.variant, flush=True)
    for b in sel:
        print("== block", b["block_id"], flush=True)
        try:
            run_one(b, args, rasterio, {})
        except Exception as e:                       # keep going with the next block; the failure is recorded
            import traceback; traceback.print_exc()
            os.makedirs(os.path.join(args.out, args.variant, "failed"), exist_ok=True)
            open(os.path.join(args.out, args.variant, "failed", b["block_id"] + ".txt"), "w").write(traceback.format_exc())


if __name__ == "__main__":
    main()
