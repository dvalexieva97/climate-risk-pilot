from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from climate_risk.config import AppConfig
from climate_risk.events.schema import HazardEvent
from climate_risk.grid import TargetGrid

logger = logging.getLogger(__name__)


class HazardProcessor(ABC):
    hazard_name: str

    @abstractmethod
    def build_hazard_layer(self, config: AppConfig, grid: TargetGrid) -> Path:
        """Produce harmonized hazard raster on target grid."""

    @abstractmethod
    def collect_historical_events(self, config: AppConfig, grid: TargetGrid) -> list[HazardEvent]:
        """Return normalized events for the configured lookback window."""

    def run(self, config: AppConfig, grid: TargetGrid) -> dict[str, Path]:
        from climate_risk.events.aggregate import write_event_count_layers
        from climate_risk.events.schema import HazardKind

        logger.info("Processing hazard: %s", self.hazard_name)
        hazard_path = self.build_hazard_layer(config, grid)
        events = self.collect_historical_events(config, grid)
        event_outputs = write_event_count_layers(
            HazardKind(self.hazard_name),
            events,
            grid,
            config,
        )
        return {"hazard": hazard_path, **event_outputs}
