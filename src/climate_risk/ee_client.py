from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import ee

from climate_risk.config import AppConfig
from climate_risk.grid import TargetGrid

logger = logging.getLogger(__name__)

_initialized = False


def _resolve_ee_project(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    for key in ("EE_PROJECT", "CLIMATE_RISK_EE_PROJECT", "GOOGLE_CLOUD_PROJECT"):
        if os.environ.get(key):
            return os.environ[key]
    creds_path = Path.home() / ".config" / "earthengine" / "credentials"
    if creds_path.exists():
        try:
            data = json.loads(creds_path.read_text())
            if data.get("project"):
                return data["project"]
        except (json.JSONDecodeError, OSError):
            pass
    return None


def init_earth_engine(project: str | None = None) -> None:
    global _initialized
    if _initialized:
        return
    project = _resolve_ee_project(project)
    try:
        if project:
            ee.Initialize(project=project)
            logger.info("Earth Engine initialized (project=%s)", project)
        else:
            ee.Initialize()
            logger.info("Earth Engine initialized")
        _initialized = True
    except Exception as exc:
        raise RuntimeError(
            "Earth Engine not authenticated. Run: earthengine authenticate && "
            "earthengine set_project YOUR_GCP_PROJECT"
        ) from exc


def region_geometry(config: AppConfig) -> ee.Geometry:
    return ee.Geometry.Rectangle(list(config.region.bbox_wgs84), proj=None, geodesic=False)


def export_image_to_drive_or_local(
    image: ee.Image,
    description: str,
    region: ee.Geometry,
    scale: int,
    local_path: Path,
    *,
    crs: str = "EPSG:3035",
    max_pixels: int = 1_000_000_000,
) -> Path:
    """
    Export EE image to local GeoTIFF via getDownloadURL (pilot regions only).
    Use a coarse `scale` for heavy ImageCollection reductions; reproject to the
    target grid afterwards with align_raster_file().
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "scale": scale,
        "crs": crs,
        "region": region,
        "format": "GEO_TIFF",
        "maxPixels": max_pixels,
    }
    url = image.getDownloadURL(params)
    import requests

    logger.info("Downloading EE export %s @ %sm ...", description, scale)
    response = requests.get(url, timeout=600)
    if not response.ok:
        logger.error("EE export failed (%s): %s", response.status_code, response.text[:500])
    response.raise_for_status()
    local_path.write_bytes(response.content)
    logger.info("Saved EE export to %s", local_path)
    return local_path


def export_image_to_gcs(
    image: ee.Image,
    description: str,
    region: ee.Geometry,
    scale: int,
    gcs_bucket: str,
    gcs_prefix: str,
    *,
    crs: str = "EPSG:3035",
) -> ee.batch.Task:
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=description,
        bucket=gcs_bucket,
        fileNamePrefix=gcs_prefix,
        region=region,
        scale=scale,
        crs=crs,
        maxPixels=1_000_000_000,
        fileFormat="GeoTIFF",
    )
    task.start()
    return task


def wait_for_task(task: ee.batch.Task, poll_interval: int = 10) -> None:
    while task.active():
        time.sleep(poll_interval)
    status = task.status()
    if status.get("state") != "COMPLETED":
        raise RuntimeError(f"EE task failed: {status}")
