from __future__ import annotations

import logging
from datetime import datetime

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box

logger = logging.getLogger(__name__)

# GloFAS/EFFIS-style event layers vary; this fetcher uses the JRC EFAS WFS when available
# and falls back to empty GeoDataFrame with correct schema.
EFAS_WFS_BASE = "https://ows.globalfloods.eu/glofas-ows/ows.php"


def fetch_efas_flood_events(
    bbox_wgs84: tuple[float, float, float, float],
    *,
    start_year: int,
    end_year: int,
) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bbox_wgs84
    bbox = box(minx, miny, maxx, maxy)
    columns = ["date", "severity", "geometry"]

    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typename": "efas:flood_events",
        "bbox": f"{miny},{minx},{maxy},{maxx}",
        "outputFormat": "application/json",
    }
    try:
        response = requests.get(EFAS_WFS_BASE, params=params, timeout=120)
        response.raise_for_status()
        gdf = gpd.read_file(response.text)
        if gdf.empty:
            logger.warning("EFAS WFS returned no flood events for bbox")
            return gpd.GeoDataFrame(columns=columns, geometry="geometry", crs="EPSG:4326")

        # Normalize date column
        for col in ("date", "start_date", "event_date", "datetime"):
            if col in gdf.columns:
                gdf["date"] = pd.to_datetime(gdf[col], errors="coerce")
                break

        if "date" in gdf.columns:
            gdf = gdf[gdf["date"].notna()]
            gdf = gdf[
                (gdf["date"].dt.year >= start_year) & (gdf["date"].dt.year <= end_year)
            ]

        gdf = gdf.to_crs("EPSG:4326")
        gdf = gdf[gdf.intersects(bbox)]
        return gdf
    except Exception as exc:
        logger.warning("Could not fetch EFAS flood events (%s). Returning empty catalog.", exc)
        return gpd.GeoDataFrame(columns=columns, geometry="geometry", crs="EPSG:4326")
