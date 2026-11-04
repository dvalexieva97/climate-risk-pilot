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

# Global Fire Weather Database (GFWED) — daily FWI, ~50 km native resolution
GFWED_IC = "projects/climate-engine-pro/assets/ce-merra2_fwi-daily"


class WildfireProcessor(HazardProcessor):
    hazard_name = "wildfire"

    def build_hazard_layer(self, config: AppConfig, grid: TargetGrid) -> Path:
        out_dir = config.paths.processed_dir / "wildfire"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / "fwi_p90_summer_raw.tif"
        aligned_path = out_dir / "fwi_p90_summer.tif"
        cog_path = out_dir / "fwi_p90_summer_cog.tif"

        init_earth_engine()
        region = region_geometry(config)

        summer = (
            ee.ImageCollection(GFWED_IC)
            .filter(ee.Filter.calendarRange(6, 9, "month"))
            .filterDate("2000-01-01", "2020-12-31")
            .select("FWI")
            .reduce(ee.Reducer.percentile([90]))
            .rename("fwi_p90")
            .clip(region)
        )

        export_image_to_drive_or_local(
            summer,
            description="portugal_fwi_p90",
            region=region,
            scale=50_000,  # GFWED native ~50 km; upsample to grid after download
            local_path=raw_path,
            crs=grid.crs,
        )
        align_raster_file(raw_path, grid, aligned_path)
        if config.export.get("cog", True):
            write_cog(aligned_path, cog_path, compress=config.export.get("compress", "DEFLATE"))
            return cog_path
        return aligned_path

    def collect_historical_events(self, config: AppConfig, grid: TargetGrid) -> list[HazardEvent]:
        from climate_risk.acquisition.wildfire_events import fetch_effis_burnt_areas

        start = config.event_history.start_year
        end = config.event_history.resolved_end_year
    # EFFIS poly layers exist from ~2016; cap at last complete calendar year
    import datetime

    effis_end = min(end, datetime.datetime.utcnow().year - 1)
        cache_dir = config.paths.raw_dir / "effis"
        gdf = fetch_effis_burnt_areas(
            config.region.bbox_wgs84,
            start_year=start,
            end_year=effis_end,
            cache_dir=cache_dir,
        )
        events: list[HazardEvent] = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue

            def _to_date(val):
                if val is None:
                    return None
                if hasattr(val, "date"):
                    return val.date()
                if isinstance(val, str):
                    return date.fromisoformat(val[:10])
                return None

            start_date = _to_date(row.get("start_date") or row.get("date"))
            end_date = _to_date(row.get("end_date") or row.get("start_date"))
            events.append(
                HazardEvent(
                    event_id=str(row.get("id", f"fire_{idx}")),
                    hazard=HazardKind.WILDFIRE,
                    start_date=start_date,
                    end_date=end_date,
                    geometry_wkt=geom.wkt,
                    source="EFFIS burnt areas",
                    intensity=float(row["area_ha"]) if row.get("area_ha") is not None else None,
                    intensity_unit="ha",
                    metadata={k: row[k] for k in ("country", "province") if k in row and row[k] is not None},
                )
            )
        logger.info("Collected %d wildfire events (%d–%d)", len(events), start, end)
        return events
