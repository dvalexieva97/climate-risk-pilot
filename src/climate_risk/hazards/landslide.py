from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from rasterio.enums import Resampling

from climate_risk.config import AppConfig
from climate_risk.events.schema import HazardEvent, HazardKind
from climate_risk.export.cog import align_raster_file, reproject_to_grid, write_array, write_cog
from climate_risk.grid import TargetGrid
from climate_risk.hazards.base import HazardProcessor

logger = logging.getLogger(__name__)


class LandslideProcessor(HazardProcessor):
    hazard_name = "landslide"

    def build_hazard_layer(self, config: AppConfig, grid: TargetGrid) -> Path:
        hazard_cfg = config.hazards["landslide"]
        elsus_path = Path(hazard_cfg["elsus_raw_path"])
        if not elsus_path.exists():
            raise FileNotFoundError(
                f"ELSUS v2 raster not found at {elsus_path}. "
                "Register at https://esdac.jrc.ec.europa.eu/content/european-landslide-susceptibility-map-elsus-v2 "
                "and set hazards.landslide.elsus_raw_path or ELSUS_RAW_PATH."
            )

        out_dir = config.paths.processed_dir / "landslide"
        out_dir.mkdir(parents=True, exist_ok=True)
        aligned_path = out_dir / "elsus_susceptibility.tif"
        cog_path = out_dir / "elsus_susceptibility_cog.tif"

        # ELSUS is categorical susceptibility 0–4; use nearest neighbour
        data, _ = reproject_to_grid(
            elsus_path,
            grid,
            resampling=Resampling.nearest,
        )
        write_array(aligned_path, data, grid, dtype="uint8", nodata=0)
        if config.export.get("cog", True):
            write_cog(aligned_path, cog_path, compress=config.export.get("compress", "DEFLATE"))
            return cog_path
        return aligned_path

    def collect_historical_events(self, config: AppConfig, grid: TargetGrid) -> list[HazardEvent]:
        from climate_risk.acquisition.landslide_events import fetch_jrc_landslide_inventory

        start = config.event_history.start_year
        end = config.event_history.resolved_end_year
        gdf = fetch_jrc_landslide_inventory(config.region.bbox_wgs84, start_year=start, end_year=end)
        events: list[HazardEvent] = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            event_date = row.get("date") or row.get("event_date")
            if hasattr(event_date, "date"):
                event_date = event_date.date()
            elif isinstance(event_date, str) and event_date:
                event_date = date.fromisoformat(event_date[:10])
            else:
                event_date = None
            events.append(
                HazardEvent(
                    event_id=str(row.get("event_id", f"landslide_{idx}")),
                    hazard=HazardKind.LANDSLIDE,
                    start_date=event_date,
                    end_date=event_date,
                    geometry_wkt=geom.wkt,
                    source="JRC European landslide inventory",
                    intensity=float(row["severity"]) if row.get("severity") is not None else None,
                    intensity_unit="ordinal" if row.get("severity") is not None else None,
                    metadata={
                        k: row[k]
                        for k in ("country", "location", "trigger", "landslide_type")
                        if k in row and row[k] is not None
                    },
                )
            )
        logger.info("Collected %d landslide events (%d–%d)", len(events), start, end)
        return events
