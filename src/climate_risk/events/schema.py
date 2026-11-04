from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from enum import Enum
from typing import Any


class HazardKind(str, Enum):
    FLOOD = "flood"
    WILDFIRE = "wildfire"
    DROUGHT = "drought"
    LANDSLIDE = "landslide"


@dataclass
class HazardEvent:
    """Normalized historical event record stored in the events catalog."""

    event_id: str
    hazard: HazardKind
    start_date: date | None
    end_date: date | None
    geometry_wkt: str
    source: str
    intensity: float | None = None
    intensity_unit: str | None = None
    metadata: dict[str, Any] | None = None

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["hazard"] = self.hazard.value
        row["start_date"] = self.start_date.isoformat() if self.start_date else None
        row["end_date"] = self.end_date.isoformat() if self.end_date else None
        return row
