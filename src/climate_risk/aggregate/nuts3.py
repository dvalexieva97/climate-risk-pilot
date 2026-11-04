from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

from climate_risk.config import AppConfig
from climate_risk.grid import TargetGrid

logger = logging.getLogger(__name__)


def load_nuts3_for_region(config: AppConfig) -> gpd.GeoDataFrame:
    root = Path(__file__).resolve().parents[3]
    nuts_path = root / "data" / "reference" / f"nuts3_{config.region.name}.geojson"
    if not nuts_path.exists():
        logger.warning("NUTS3 reference file missing: %s — skipping zonal stats", nuts_path)
        return gpd.GeoDataFrame(columns=["NUTS_ID", "NAME_LATN", "geometry"], crs=config.grid.crs)
    return gpd.read_file(nuts_path).to_crs(config.grid.crs)


def zonal_stats_for_raster(
    raster_path: Path,
    zones: gpd.GeoDataFrame,
    *,
    stat_names: tuple[str, ...] = ("mean", "max", "p90"),
) -> dict[str, list[float | int | None]]:
    stats: dict[str, list[float | int | None]] = {s: [] for s in stat_names}
    with rasterio.open(raster_path) as src:
        nodata = src.nodata
        for _, zone in zones.iterrows():
            geom = [mapping(zone.geometry)]
            try:
                data, _ = mask(src, geom, crop=True, nodata=nodata)
                arr = data[0].astype("float64")
                if nodata is not None:
                    arr = np.where(arr == nodata, np.nan, arr)
                valid = arr[~np.isnan(arr)]
            except ValueError:
                valid = np.array([])

            if valid.size == 0:
                for s in stat_names:
                    stats[s].append(np.nan)
                continue
            if "mean" in stat_names:
                stats["mean"].append(float(np.nanmean(valid)))
            if "max" in stat_names:
                stats["max"].append(float(np.nanmax(valid)))
            if "p90" in stat_names:
                stats["p90"].append(float(np.nanpercentile(valid, 90)))
            if "sum" in stat_names:
                stats["sum"].append(float(np.nansum(valid)))
    return stats


def aggregate_all_hazards(
    config: AppConfig,
    grid: TargetGrid,
    hazard_outputs: dict[str, dict[str, Path]],
) -> Path:
    zones = load_nuts3_for_region(config)
    out_dir = config.paths.processed_dir / "nuts3"
    out_dir.mkdir(parents=True, exist_ok=True)

    if zones.empty:
        out_path = out_dir / "hazard_summary.parquet"
        pd.DataFrame().to_parquet(out_path)
        return out_path

    merged = zones[["NUTS_ID", "NAME_LATN"]].copy()

    for hazard, outputs in hazard_outputs.items():
        hazard_raster = outputs.get("hazard")
        if hazard_raster and hazard_raster.exists():
            hstats = zonal_stats_for_raster(hazard_raster, zones)
            merged[f"{hazard}_mean"] = hstats.get("mean", [])
            merged[f"{hazard}_max"] = hstats.get("max", [])
            merged[f"{hazard}_p90"] = hstats.get("p90", [])

        event_raster = outputs.get("event_count")
        if event_raster and event_raster.exists():
            estats = zonal_stats_for_raster(event_raster, zones, stat_names=("mean", "max", "sum"))
            merged[f"{hazard}_events_mean"] = estats.get("mean", [])
            merged[f"{hazard}_events_max"] = estats.get("max", [])
            merged[f"{hazard}_events_sum"] = estats.get("sum", [])

    out_parquet = out_dir / "hazard_summary.parquet"
    out_csv = out_dir / "hazard_summary.csv"
    merged.to_parquet(out_parquet, index=False)
    merged.to_csv(out_csv, index=False)

    manifest = {
        "region": config.region.name,
        "nuts3_units": int(len(zones)),
        "hazards": list(hazard_outputs.keys()),
        "outputs": {"parquet": str(out_parquet), "csv": str(out_csv)},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info("NUTS3 summary written to %s", out_parquet)
    return out_parquet
