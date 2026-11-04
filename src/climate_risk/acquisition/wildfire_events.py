from __future__ import annotations

import logging
from datetime import date
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box

logger = logging.getLogger(__name__)

# Copernicus EFFIS mapserv — per-year burned area polygon layers (2016+)
EFFIS_WFS = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_LAYER_FMT = "modis.ba.poly.{year}"


def fetch_effis_burnt_areas(
    bbox_wgs84: tuple[float, float, float, float],
    *,
    start_year: int,
    end_year: int,
    cache_dir: Path | None = None,
) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bbox_wgs84
    bbox_geom = box(minx, miny, maxx, maxy)
    frames: list[gpd.GeoDataFrame] = []

    for year in range(start_year, end_year + 1):
        if year < 2016:
            continue  # EFFIS WFS poly layers start ~2016
        try:
            if cache_dir:
                cache_path = cache_dir / f"effis_ba_{year}.geojson"
                if cache_path.exists():
                    gdf = gpd.read_file(cache_path)
                else:
                    gdf = _fetch_effis_year(year, bbox_wgs84)
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    if not gdf.empty:
                        gdf.to_file(cache_path, driver="GeoJSON")
            else:
                gdf = _fetch_effis_year(year, bbox_wgs84)
        except Exception as exc:
            logger.warning("EFFIS burnt areas %d failed: %s", year, exc)
            continue

        if gdf.empty:
            continue
        gdf = gdf.to_crs("EPSG:4326")
        gdf = gdf[gdf.intersects(bbox_geom)]
        if gdf.empty:
            continue

        for col in ("initialdate", "finaldate", "date", "firedate", "FIREDATE"):
            if col in gdf.columns:
                gdf["start_date"] = pd.to_datetime(gdf[col], errors="coerce")
                break
        for col in ("finaldate", "FINALDATE"):
            if col in gdf.columns:
                gdf["end_date"] = pd.to_datetime(gdf[col], errors="coerce")
                break
        if "end_date" not in gdf.columns:
            gdf["end_date"] = gdf.get("start_date")

        if "area_ha" not in gdf.columns:
            for col in ("AREA_HA", "area", "area_ha", "burnt_ha", "ha"):
                if col in gdf.columns:
                    gdf["area_ha"] = pd.to_numeric(gdf[col], errors="coerce")
                    break

        if "id" not in gdf.columns or gdf["id"].isna().all():
            gdf["id"] = [f"effis_{year}_{i}" for i in range(len(gdf))]
        if "country" not in gdf.columns and "COUNTRY" in gdf.columns:
            gdf["country"] = gdf["COUNTRY"]
        if "province" not in gdf.columns and "PROVINCE" in gdf.columns:
            gdf["province"] = gdf["PROVINCE"]
        frames.append(gdf)

    if not frames:
        logger.warning("No EFFIS burnt area features found for %d–%d", start_year, end_year)
        return gpd.GeoDataFrame(
            columns=["id", "start_date", "end_date", "area_ha", "geometry"],
            geometry="geometry",
            crs="EPSG:4326",
        )

    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def _fetch_effis_year(year: int, bbox_wgs84: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = bbox_wgs84
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typename": EFFIS_LAYER_FMT.format(year=year),
        "srsName": "EPSG:4326",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
    }
    response = requests.get(EFFIS_WFS, params=params, timeout=180)
    response.raise_for_status()
    if not response.content.strip():
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    gdf = gpd.read_file(BytesIO(response.content), driver="GML")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf
