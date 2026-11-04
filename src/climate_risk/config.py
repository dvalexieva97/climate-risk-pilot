from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RegionConfig:
    name: str
    label: str
    bbox_wgs84: tuple[float, float, float, float]


@dataclass
class GridConfig:
    crs: str
    resolution_m: int
    nodata: float


@dataclass
class EventHistoryConfig:
    years: int
    end_year: int | None

    @property
    def start_year(self) -> int:
        end = self.end_year or datetime.utcnow().year
        return end - self.years + 1

    @property
    def resolved_end_year(self) -> int:
        return self.end_year or datetime.utcnow().year


@dataclass
class PathsConfig:
    raw_dir: Path
    processed_dir: Path
    events_dir: Path
    catalog_dir: Path


@dataclass
class GcsConfig:
    bucket: str | None
    prefix: str
    upload: bool


@dataclass
class AppConfig:
    region: RegionConfig
    grid: GridConfig
    event_history: EventHistoryConfig
    hazards: dict[str, Any]
    paths: PathsConfig
    gcs: GcsConfig
    export: dict[str, Any]
    nuts3: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    region_config_path: str | Path,
    defaults_path: str | Path | None = None,
) -> AppConfig:
    root = Path(__file__).resolve().parents[2]
    defaults_file = Path(defaults_path) if defaults_path else root / "config" / "default.yaml"
    region_file = Path(region_config_path)
    if not region_file.is_absolute():
        region_file = root / region_file

    with defaults_file.open() as f:
        data = yaml.safe_load(f) or {}
    with region_file.open() as f:
        data = _deep_merge(data, yaml.safe_load(f) or {})

    region = data["region"]
    grid = data["grid"]
    event = data.get("event_history", {})
    paths = data["paths"]
    gcs = data.get("gcs", {})

    elsus_env = os.environ.get("ELSUS_RAW_PATH")
    if elsus_env and "landslide" in data.get("hazards", {}):
        data["hazards"]["landslide"]["elsus_raw_path"] = elsus_env

    bucket = os.environ.get("CLIMATE_RISK_GCS_BUCKET") or gcs.get("bucket")
    upload = os.environ.get("CLIMATE_RISK_GCS_UPLOAD", str(gcs.get("upload", False))).lower() in (
        "1",
        "true",
        "yes",
    )

    events_dir = paths["events_dir"]
    catalog_dir = paths.get("catalog_dir", f"{events_dir}/catalog")

    root_path = root
    return AppConfig(
        region=RegionConfig(
            name=region["name"],
            label=region.get("label", region["name"]),
            bbox_wgs84=tuple(region["bbox_wgs84"]),
        ),
        grid=GridConfig(
            crs=grid["crs"],
            resolution_m=int(grid["resolution_m"]),
            nodata=float(grid.get("nodata", -9999)),
        ),
        event_history=EventHistoryConfig(
            years=int(event.get("years", 20)),
            end_year=event.get("end_year"),
        ),
        hazards=data.get("hazards", {}),
        paths=PathsConfig(
            raw_dir=(root_path / paths["raw_dir"]).resolve(),
            processed_dir=(root_path / paths["processed_dir"]).resolve(),
            events_dir=(root_path / paths["events_dir"]).resolve(),
            catalog_dir=(root_path / catalog_dir).resolve(),
        ),
        gcs=GcsConfig(bucket=bucket, prefix=gcs.get("prefix", "climate-risk/v0"), upload=upload),
        export=data.get("export", {}),
        nuts3=data.get("nuts3", {}),
        raw=data,
    )


def ensure_dirs(config: AppConfig) -> None:
    for path in (
        config.paths.raw_dir,
        config.paths.processed_dir,
        config.paths.events_dir,
        config.paths.catalog_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
