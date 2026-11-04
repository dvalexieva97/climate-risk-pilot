from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as shapely_transform

from climate_risk.config import AppConfig


@dataclass(frozen=True)
class TargetGrid:
    crs: str
    transform: rasterio.Affine
    width: int
    height: int
    bounds: tuple[float, float, float, float]
    nodata: float

    def profile(self, dtype: str = "float32", count: int = 1) -> dict:
        return {
            "driver": "GTiff",
            "height": self.height,
            "width": self.width,
            "count": count,
            "dtype": dtype,
            "crs": self.crs,
            "transform": self.transform,
            "nodata": self.nodata,
        }


def wgs84_bbox_to_projected(
    bbox_wgs84: tuple[float, float, float, float],
    target_crs: str,
) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bbox_wgs84
    poly = box(minx, miny, maxx, maxy)
    transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    projected = shapely_transform(transformer.transform, poly)
    return projected.bounds


def build_target_grid(config: AppConfig) -> TargetGrid:
    minx, miny, maxx, maxy = wgs84_bbox_to_projected(
        config.region.bbox_wgs84,
        config.grid.crs,
    )
    res = config.grid.resolution_m
    width = int(np.ceil((maxx - minx) / res))
    height = int(np.ceil((maxy - miny) / res))
    # Snap origin to resolution grid
    minx = np.floor(minx / res) * res
    maxy = np.ceil(maxy / res) * res
    width = int(np.ceil((maxx - minx) / res))
    height = int(np.ceil((maxy - miny) / res))
    transform = from_origin(minx, maxy, res, res)
    bounds = (minx, maxy - height * res, minx + width * res, maxy)
    return TargetGrid(
        crs=config.grid.crs,
        transform=transform,
        width=width,
        height=height,
        bounds=bounds,
        nodata=config.grid.nodata,
    )


def grid_footprint_geojson(grid: TargetGrid) -> dict:
    minx, miny, maxx, maxy = grid.bounds
    geom = box(minx, miny, maxx, maxy)
    return mapping(geom)


def region_bbox_geojson(config: AppConfig) -> dict:
    return mapping(box(*config.region.bbox_wgs84))
