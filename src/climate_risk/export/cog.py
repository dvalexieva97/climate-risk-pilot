from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject, calculate_default_transform
from rasterio.shutil import copy as rio_copy

from climate_risk.grid import TargetGrid


def write_array(
    path: Path,
    data,
    grid: TargetGrid,
    dtype: str = "float32",
    nodata: float | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = grid.profile(dtype=dtype)
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype), 1)
    return path


def reproject_to_grid(
    src_path: Path,
    grid: TargetGrid,
    *,
    resampling: Resampling = Resampling.bilinear,
    src_nodata: float | None = None,
    dst_nodata: float | None = None,
) -> tuple:
    dst_nodata = grid.nodata if dst_nodata is None else dst_nodata
    with rasterio.open(src_path) as src:
        destination = __import__("numpy").zeros((grid.height, grid.width), dtype="float32")
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            src_nodata=src_nodata if src_nodata is not None else src.nodata,
            dst_nodata=dst_nodata,
            resampling=resampling,
        )
    return destination, grid.profile()


def write_cog(
    src_path: Path,
    dst_path: Path,
    *,
    compress: str = "DEFLATE",
    overview_levels: list[int] | None = None,
) -> Path:
    """Convert GeoTIFF to Cloud Optimized GeoTIFF."""
    overview_levels = overview_levels or [2, 4, 8, 16]
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "compress": compress,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "interleave": "band",
        "BIGTIFF": "IF_SAVED",
    }
    with rasterio.open(src_path) as src:
        profile.update(src.profile)
        profile.update(
            {
                "driver": "GTiff",
                "compress": compress,
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512,
            }
        )
        if profile.get("BIGTIFF") == "IF_SAVED":
            del profile["BIGTIFF"]
        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(1, src.count + 1):
                dst.write(src.read(i), i)
            dst.build_overviews(overview_levels, Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")
    return dst_path


def align_raster_file(
    src_path: Path,
    grid: TargetGrid,
    dst_path: Path,
    *,
    resampling: Resampling = Resampling.bilinear,
) -> Path:
    data, _ = reproject_to_grid(src_path, grid, resampling=resampling)
    write_array(dst_path, data, grid)
    return dst_path
