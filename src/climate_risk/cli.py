from __future__ import annotations

import logging
from pathlib import Path

import click

from climate_risk.pipeline.run_pilot import run_from_config_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


@click.group()
def main() -> None:
    """Europe climate risk assessment CLI."""


@main.command("run-pilot")
@click.option(
    "--config",
    "config_path",
    default="config/pilot_portugal.yaml",
    show_default=True,
    type=click.Path(exists=True, path_type=Path),
    help="Region YAML config (merged with config/default.yaml).",
)
@click.option(
    "--hazard",
    "hazards",
    multiple=True,
    type=click.Choice(["flood", "wildfire", "drought", "landslide"]),
    help="Run only selected hazards (default: all enabled).",
)
@click.option("--upload-gcs", is_flag=True, help="Upload outputs to GCS (requires bucket env).")
def run_pilot_cmd(config_path: Path, hazards: tuple[str, ...], upload_gcs: bool) -> None:
    """Run Portugal (or other pilot) hazard + event-history pipeline."""
    import os

    if upload_gcs:
        os.environ["CLIMATE_RISK_GCS_UPLOAD"] = "true"
    hazard_list = list(hazards) if hazards else None
    result = run_from_config_path(config_path, hazards=hazard_list)
    click.echo(f"Done. Manifest: {result['manifest']}")


@main.command("grid-info")
@click.option("--config", "config_path", default="config/pilot_portugal.yaml", type=click.Path(exists=True))
def grid_info(config_path: Path) -> None:
    """Print target grid dimensions for a region config."""
    from climate_risk.config import load_config
    from climate_risk.grid import build_target_grid

    config = load_config(config_path)
    grid = build_target_grid(config)
    click.echo(
        f"{config.region.label}: {grid.width}x{grid.height} pixels @ {config.grid.resolution_m}m "
        f"({grid.crs})"
    )


if __name__ == "__main__":
    main()
