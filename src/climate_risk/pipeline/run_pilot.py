from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from climate_risk.aggregate.nuts3 import aggregate_all_hazards
from climate_risk.config import AppConfig, ensure_dirs, load_config
from climate_risk.gcs import upload_tree
from climate_risk.grid import build_target_grid
from climate_risk.hazards.drought import DroughtProcessor
from climate_risk.hazards.flood import FloodProcessor
from climate_risk.hazards.landslide import LandslideProcessor
from climate_risk.hazards.wildfire import WildfireProcessor

logger = logging.getLogger(__name__)

PROCESSORS = {
    "flood": FloodProcessor,
    "wildfire": WildfireProcessor,
    "drought": DroughtProcessor,
    "landslide": LandslideProcessor,
}


def run_pilot(config: AppConfig, *, hazards: list[str] | None = None) -> dict:
    ensure_dirs(config)
    grid = build_target_grid(config)
    grid_meta = {
        "crs": grid.crs,
        "width": grid.width,
        "height": grid.height,
        "resolution_m": config.grid.resolution_m,
        "bounds": grid.bounds,
        "region": config.region.name,
    }
    grid_path = config.paths.processed_dir / "grid.json"
    grid_path.write_text(json.dumps(grid_meta, indent=2))

    selected = hazards or [k for k, v in config.hazards.items() if v.get("enabled", True)]
    hazard_outputs: dict[str, dict[str, Path]] = {}

    for name in selected:
        if name not in PROCESSORS:
            raise ValueError(f"Unknown hazard: {name}")
        if not config.hazards.get(name, {}).get("enabled", True):
            logger.info("Skipping disabled hazard: %s", name)
            continue
        processor = PROCESSORS[name]()
        try:
            hazard_outputs[name] = processor.run(config, grid)
        except FileNotFoundError as exc:
            logger.error("Skipping %s — missing input data: %s", name, exc)

    if config.nuts3.get("enabled", True):
        aggregate_all_hazards(config, grid, hazard_outputs)

    manifest = build_manifest(config, grid, hazard_outputs)
    manifest_path = config.paths.processed_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    if config.gcs.upload and config.gcs.bucket:
        upload_tree(config.paths.processed_dir, config)
        upload_tree(config.paths.events_dir, config)

    return {"grid": grid_meta, "hazards": hazard_outputs, "manifest": manifest_path}


def build_manifest(
    config: AppConfig,
    grid,
    hazard_outputs: dict[str, dict[str, Path]],
) -> dict:
    years = config.event_history.years
    return {
        "version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": {
            "name": config.region.name,
            "label": config.region.label,
            "bbox_wgs84": config.region.bbox_wgs84,
        },
        "grid": {
            "crs": grid.crs,
            "resolution_m": config.grid.resolution_m,
            "width": grid.width,
            "height": grid.height,
        },
        "event_history": {
            "years": years,
            "start_year": config.event_history.start_year,
            "end_year": config.event_history.resolved_end_year,
        },
        "layers": {
            hazard: {k: str(v) for k, v in paths.items()}
            for hazard, paths in hazard_outputs.items()
        },
        "methodology": {
            "framework": "IPCC AR5/AR6 Hazard x Exposure x Vulnerability (hazard-only in V0)",
            "hazard_metrics": {
                "flood": "JRC GloFAS inundation depth (return period)",
                "wildfire": "FWI 90th percentile Jun-Sep",
                "drought": "SPI-12 vs 1991-2020 baseline",
                "landslide": "ELSUS v2 susceptibility class (not probabilistic hazard)",
            },
            "event_layers": {
                "description": (
                    "Per-cell event counts and vector catalogs for the configured lookback window"
                ),
                "catalog_format": "parquet (GeoParquet)",
                "count_raster": f"event_count_{years}y.tif",
            },
        },
    }


def run_from_config_path(config_path: str | Path, hazards: list[str] | None = None) -> dict:
    config = load_config(config_path)
    return run_pilot(config, hazards=hazards)
