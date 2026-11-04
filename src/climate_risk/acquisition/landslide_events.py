from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box

logger = logging.getLogger(__name__)

# JRC landslide hazard project inventory (registration may be required for bulk download)
JRC_LANDSLIDE_SAMPLE = (
    "https://raw.githubusercontent.com/climaax/notebooks/main/data/sample/landslides.geojson"
)


def fetch_jrc_landslide_inventory(
    bbox_wgs84: tuple[float, float, float, float],
    *,
    start_year: int,
    end_year: int,
    local_path: Path | None = None,
) -> gpd.GeoDataFrame:
    """
    Load landslide event points intersecting the region and time window.

    Place official JRC inventory GeoJSON/Shapefile at data/raw/landslides/inventory.geojson
    or pass local_path. Falls back to empty catalog if unavailable.
    """
    minx, miny, maxx, maxy = bbox_wgs84
    bbox = box(minx, miny, maxx, maxy)
    default_local = Path("data/raw/portugal/landslides/inventory.geojson")

    for candidate in (local_path, default_local):
        if candidate and Path(candidate).exists():
            gdf = gpd.read_file(candidate)
            return _filter_inventory(gdf, bbox, start_year, end_year)

    logger.warning(
        "JRC landslide inventory not found locally. "
        "Download from ESDAC and save to data/raw/portugal/landslides/inventory.geojson"
    )
    return gpd.GeoDataFrame(
        columns=["event_id", "date", "severity", "geometry"],
        geometry="geometry",
        crs="EPSG:4326",
    )


def _filter_inventory(
    gdf: gpd.GeoDataFrame,
    bbox,
    start_year: int,
    end_year: int,
) -> gpd.GeoDataFrame:
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[gdf.intersects(bbox)]
    date_col = next((c for c in ("date", "event_date", "year") if c in gdf.columns), None)
    if date_col:
        if date_col == "year":
            gdf["date"] = pd.to_datetime(gdf["year"].astype(str) + "-06-01")
        else:
            gdf["date"] = pd.to_datetime(gdf[date_col], errors="coerce")
        gdf = gdf[gdf["date"].notna()]
        gdf = gdf[(gdf["date"].dt.year >= start_year) & (gdf["date"].dt.year <= end_year)]
    return gdf
