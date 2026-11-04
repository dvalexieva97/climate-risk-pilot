from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping

from climate_risk.config import AppConfig
from climate_risk.events.schema import HazardEvent, HazardKind
from climate_risk.export.cog import write_array, write_cog
from climate_risk.grid import TargetGrid

logger = logging.getLogger(__name__)


def save_event_catalog(events: list[HazardEvent], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "event_id",
        "hazard",
        "start_date",
        "end_date",
        "geometry_wkt",
        "source",
        "intensity",
        "intensity_unit",
        "metadata",
    ]
    if not events:
        gdf = gpd.GeoDataFrame(
            {c: [] for c in columns},
            geometry=gpd.GeoSeries([], crs="EPSG:4326"),
            crs="EPSG:4326",
        )
        gdf.to_parquet(path)
        return path

    rows = [e.to_row() for e in events]
    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.GeoSeries.from_wkt(df["geometry_wkt"]),
        crs="EPSG:4326",
    )
    gdf.to_parquet(path)
    logger.info("Saved %d events to %s", len(events), path)
    return path


def load_event_catalog(path: Path) -> gpd.GeoDataFrame:
    empty = gpd.GeoDataFrame(columns=["event_id", "hazard", "geometry"], geometry="geometry", crs="EPSG:4326")
    if not path.exists():
        return empty
    try:
        return gpd.read_parquet(path)
    except ValueError:
        # Empty catalog saved without geo metadata
        return empty


def rasterize_event_counts(
    events_gdf: gpd.GeoDataFrame,
    grid: TargetGrid,
    *,
    all_touched: bool = True,
) -> np.ndarray:
    if events_gdf.empty:
        return np.zeros((grid.height, grid.width), dtype=np.uint16)

    gdf = events_gdf.to_crs(grid.crs)
    counts = np.zeros((grid.height, grid.width), dtype=np.uint16)

    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        layer = rasterize(
            shapes=[(mapping(geom), 1)],
            out_shape=(grid.height, grid.width),
            transform=grid.transform,
            fill=0,
            dtype=np.uint16,
            all_touched=all_touched,
        )
        counts = counts + layer  # sum overlapping events per cell

    return counts


def write_event_count_layers(
    hazard: HazardKind,
    events: list[HazardEvent],
    grid: TargetGrid,
    config: AppConfig,
    *,
    extra_arrays: dict[str, np.ndarray] | None = None,
) -> dict[str, Path]:
    """Write catalog parquet + event-count COG (+ optional auxiliary count rasters)."""
    years = config.event_history.years
    hazard_dir = config.paths.events_dir / hazard.value
    hazard_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = config.paths.catalog_dir / f"{hazard.value}_events_{years}y.parquet"
    save_event_catalog(events, catalog_path)

    events_gdf = load_event_catalog(catalog_path)
    count_array = rasterize_event_counts(events_gdf, grid)

    raw_count = hazard_dir / f"event_count_{years}y.tif"
    write_array(raw_count, count_array, grid, dtype="uint16", nodata=0)

    cog_path = hazard_dir / f"event_count_{years}y_cog.tif"
    if config.export.get("cog", True):
        write_cog(
            raw_count,
            cog_path,
            compress=config.export.get("compress", "DEFLATE"),
            overview_levels=config.export.get("overview_levels"),
        )

    summary = {
        "hazard": hazard.value,
        "region": config.region.name,
        "event_history_years": years,
        "start_year": config.event_history.start_year,
        "end_year": config.event_history.resolved_end_year,
        "event_count": len(events),
        "cells_with_events": int(np.count_nonzero(count_array)),
        "max_events_per_cell": int(count_array.max()) if count_array.size else 0,
    }
    summary_path = hazard_dir / f"event_summary_{years}y.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    outputs = {
        "catalog": catalog_path,
        "event_count": raw_count,
        "event_count_cog": cog_path,
        "summary": summary_path,
    }

    for name, array in (extra_arrays or {}).items():
        aux_path = hazard_dir / f"{name}.tif"
        write_array(aux_path, array, grid, dtype="uint16", nodata=0)
        outputs[name] = aux_path

    return outputs
