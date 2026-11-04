from __future__ import annotations

import logging
from pathlib import Path

import ee
import numpy as np
import rasterio

from climate_risk.config import AppConfig
from climate_risk.ee_client import export_image_to_drive_or_local, init_earth_engine, region_geometry
from climate_risk.events.aggregate import write_event_count_layers
from climate_risk.events.schema import HazardEvent, HazardKind
from climate_risk.export.cog import align_raster_file, write_cog
from climate_risk.grid import TargetGrid
from climate_risk.hazards.base import HazardProcessor

logger = logging.getLogger(__name__)


class DroughtProcessor(HazardProcessor):
    hazard_name = "drought"

    def run(self, config: AppConfig, grid: TargetGrid) -> dict[str, Path]:
        hazard_path = self.build_hazard_layer(config, grid)
        events = self.collect_historical_events(config, grid)
        drought_months = self.build_drought_month_count(config, grid)
        event_outputs = write_event_count_layers(
            HazardKind.DROUGHT,
            events,
            grid,
            config,
            extra_arrays={"drought_months_below_threshold": drought_months},
        )
        return {"hazard": hazard_path, **event_outputs}

    def build_drought_month_count(self, config: AppConfig, grid: TargetGrid) -> np.ndarray:
        """Raster of months with SPI below threshold during the event-history window."""
        hazard_cfg = config.hazards["drought"]
        threshold = float(hazard_cfg.get("spi_drought_threshold", -1.5))
        start = config.event_history.start_year
        end = config.event_history.resolved_end_year

        init_earth_engine()
        region = region_geometry(config)
        precip = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").select("total_precipitation_sum")
        clim = precip.filterDate("1991-01-01", "2020-12-31")
        clim_mean = clim.mean()
        clim_std = clim.reduce(ee.Reducer.stdDev())
        coll = precip.filterDate(f"{start}-01-01", f"{end}-12-31")

        def drought_month(img: ee.Image) -> ee.Image:
            spi = img.subtract(clim_mean).divide(clim_std)
            return spi.lt(threshold).rename("dry")

        dry_months = coll.map(drought_month).sum().rename("drought_months").clip(region)
        raw_path = config.paths.events_dir / "drought" / "_drought_months_raw.tif"
        export_image_to_drive_or_local(
            dry_months,
            description="portugal_drought_months",
            region=region,
            scale=grid.transform.a,
            local_path=raw_path,
            crs=grid.crs,
        )
        aligned = config.paths.events_dir / "drought" / "_drought_months_aligned.tif"
        align_raster_file(raw_path, grid, aligned)
        with rasterio.open(aligned) as src:
            return src.read(1).astype(np.uint16)

    def build_hazard_layer(self, config: AppConfig, grid: TargetGrid) -> Path:
        hazard_cfg = config.hazards["drought"]
        out_dir = config.paths.processed_dir / "drought"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / "spi12_mean_raw.tif"
        aligned_path = out_dir / "spi12_mean.tif"
        cog_path = out_dir / "spi12_mean_cog.tif"

        init_earth_engine()
        region = region_geometry(config)

        # SPI-12 from ERA5 monthly precipitation (simplified: standardized vs 1991-2020 climatology)
        precip = (
            ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
            .select("total_precipitation_sum")
            .filterDate("1991-01-01", "2020-12-31")
        )
        mean = precip.mean()
        std = precip.reduce(ee.Reducer.stdDev())
        recent = (
            ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
            .select("total_precipitation_sum")
            .filterDate("2011-01-01", "2020-12-31")
            .mean()
        )
        spi = recent.subtract(mean).divide(std).rename("spi12")
        image = spi.clip(region)

        export_image_to_drive_or_local(
            image,
            description="portugal_spi12",
            region=region,
            scale=grid.transform.a,
            local_path=raw_path,
            crs=grid.crs,
        )
        align_raster_file(raw_path, grid, aligned_path)
        if config.export.get("cog", True):
            write_cog(aligned_path, cog_path, compress=config.export.get("compress", "DEFLATE"))
            return cog_path
        return aligned_path

    def collect_historical_events(self, config: AppConfig, grid: TargetGrid) -> list[HazardEvent]:
        from climate_risk.acquisition.drought_events import detect_spi_drought_events

        hazard_cfg = config.hazards["drought"]
        threshold = float(hazard_cfg.get("spi_drought_threshold", -1.5))
        min_months = int(hazard_cfg.get("min_drought_months", 3))
        start = config.event_history.start_year
        end = config.event_history.resolved_end_year

        events = detect_spi_drought_events(
            config.region.bbox_wgs84,
            start_year=start,
            end_year=end,
            threshold=threshold,
            min_consecutive_months=min_months,
        )
        logger.info("Collected %d drought events (%d–%d)", len(events), start, end)
        return events
