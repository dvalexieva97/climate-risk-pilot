from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import ee

from climate_risk.config import AppConfig
from climate_risk.ee_client import export_image_to_drive_or_local, init_earth_engine, region_geometry
from climate_risk.events.schema import HazardEvent, HazardKind
from climate_risk.export.cog import align_raster_file, write_cog
from climate_risk.grid import TargetGrid
from climate_risk.hazards.base import HazardProcessor

logger = logging.getLogger(__name__)

RP_BANDS = {10, 20, 50, 75, 100, 200, 500}


def _flood_band_name(return_period_years: int) -> str:
    if return_period_years not in RP_BANDS:
        raise ValueError(
            f"Unsupported flood return period {return_period_years}. "
            f"JRC GloFAS v2.1 supports: {sorted(RP_BANDS)}"
        )
    return f"RP{return_period_years}_depth"


def _load_glofas_flood_image(return_period_years: int, region: ee.Geometry) -> ee.Image:
    band = _flood_band_name(return_period_years)
    collection = ee.ImageCollection("JRC/CEMS_GLOFAS/FloodHazard/v2_1")
    sample = collection.first()
    available = sample.bandNames().getInfo()
    if band not in available:
        raise ValueError(f"Band {band} not found in GloFAS v2.1. Available: {available}")
    # Tiles are non-overlapping basins; mosaic yields full coverage.
    return collection.select(band).mosaic().rename("flood_depth").clip(region)


class FloodProcessor(HazardProcessor):
    hazard_name = "flood"

    def build_hazard_layer(self, config: AppConfig, grid: TargetGrid) -> Path:
        hazard_cfg = config.hazards["flood"]
        rp = int(hazard_cfg.get("return_period_years", 100))
        out_dir = config.paths.processed_dir / "flood"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / f"flood_depth_{rp}y_raw.tif"
        aligned_path = out_dir / f"flood_depth_{rp}y.tif"
        cog_path = out_dir / f"flood_depth_{rp}y_cog.tif"

        source = hazard_cfg.get("source", "earth_engine")
        if source == "earth_engine":
            init_earth_engine()
            region = region_geometry(config)
            image = _load_glofas_flood_image(rp, region)
            export_image_to_drive_or_local(
                image,
                description=f"portugal_flood_{rp}y",
                region=region,
                scale=grid.transform.a,
                local_path=raw_path,
                crs=grid.crs,
            )
        else:
            local_src = Path(hazard_cfg["local_path"])
            if not local_src.exists():
                raise FileNotFoundError(f"JRC flood raster not found: {local_src}")
            raw_path = local_src

        align_raster_file(raw_path, grid, aligned_path)
        if config.export.get("cog", True):
            write_cog(aligned_path, cog_path, compress=config.export.get("compress", "DEFLATE"))
            return cog_path
        return aligned_path

    def collect_historical_events(self, config: AppConfig, grid: TargetGrid) -> list[HazardEvent]:
        from climate_risk.acquisition.flood_events import fetch_efas_flood_events

        start = config.event_history.start_year
        end = config.event_history.resolved_end_year
        gdf = fetch_efas_flood_events(config.region.bbox_wgs84, start_year=start, end_year=end)
        events: list[HazardEvent] = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            event_date = row.get("date") or row.get("start_date")
            if hasattr(event_date, "date"):
                event_date = event_date.date()
            elif isinstance(event_date, str):
                event_date = date.fromisoformat(event_date[:10])
            else:
                event_date = None
            events.append(
                HazardEvent(
                    event_id=f"flood_{idx}",
                    hazard=HazardKind.FLOOD,
                    start_date=event_date,
                    end_date=event_date,
                    geometry_wkt=geom.wkt,
                    source="EFAS/GloFAS flood events",
                    intensity=row.get("severity") if "severity" in row else None,
                    intensity_unit="ordinal" if "severity" in row else None,
                    metadata={k: row[k] for k in row.index if k not in ("geometry",) and row[k] is not None},
                )
            )
        logger.info("Collected %d flood events (%d–%d)", len(events), start, end)
        return events
