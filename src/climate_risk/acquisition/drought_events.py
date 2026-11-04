from __future__ import annotations

import logging
from datetime import date

import ee
from shapely.geometry import box

from climate_risk.ee_client import init_earth_engine
from climate_risk.events.schema import HazardEvent, HazardKind

logger = logging.getLogger(__name__)


def _append_spell(
    events: list[HazardEvent],
    spell_idx: int,
    spell_start: date,
    end_year: int,
    end_month: int,
    spell_len: int,
    region_wkt: str,
    threshold: float,
) -> int:
    events.append(
        HazardEvent(
            event_id=f"drought_pt_{spell_idx}",
            hazard=HazardKind.DROUGHT,
            start_date=spell_start,
            end_date=date(end_year, end_month, 1),
            geometry_wkt=region_wkt,
            source="ERA5-Land SPI regional episodes",
            intensity=threshold,
            intensity_unit="spi",
            metadata={"months": spell_len, "threshold": threshold},
        )
    )
    return spell_idx + 1


def detect_spi_drought_events(
    bbox_wgs84: tuple[float, float, float, float],
    *,
    start_year: int,
    end_year: int,
    threshold: float = -1.5,
    min_consecutive_months: int = 3,
) -> list[HazardEvent]:
    """
    Detect regional drought episodes from ERA5-Land monthly precipitation SPI.

    V0 stores polygon events for Portugal-scale drought spells. Per-cell drought
    month counts are exported separately in the drought hazard pipeline.
    """
    init_earth_engine()
    region = ee.Geometry.Rectangle(list(bbox_wgs84))
    minx, miny, maxx, maxy = bbox_wgs84
    region_wkt = box(minx, miny, maxx, maxy).wkt

    precip = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR").select("total_precipitation_sum")
    clim = precip.filterDate("1991-01-01", "2020-12-31")
    clim_mean = clim.mean()
    clim_std = clim.reduce(ee.Reducer.stdDev())
    coll = precip.filterDate(f"{start_year}-01-01", f"{end_year}-12-31")

    def monthly_spi(img: ee.Image) -> ee.Image:
        spi = img.subtract(clim_mean).divide(clim_std).rename("spi")
        return spi.copyProperties(img, ["system:time_start"])

    spi_series = coll.map(monthly_spi)
    spi_list = spi_series.toList(spi_series.size())
    size = spi_series.size().getInfo()

    events: list[HazardEvent] = []
    spell_start: date | None = None
    spell_len = 0
    spell_idx = 0
    last_year, last_month = end_year, 12

    for i in range(size):
        img = ee.Image(spi_list.get(i))
        ts = ee.Date(img.get("system:time_start")).format("YYYY-MM").getInfo()
        year, month = map(int, ts.split("-"))
        last_year, last_month = year, month
        mean_spi = img.reduceRegion(ee.Reducer.mean(), region, scale=25000, maxPixels=1e9).get("spi")
        val = mean_spi.getInfo() if mean_spi is not None else None
        in_drought = val is not None and val < threshold

        if in_drought:
            if spell_len == 0:
                spell_start = date(year, month, 1)
            spell_len += 1
            continue

        if spell_len >= min_consecutive_months and spell_start:
            spell_idx = _append_spell(
                events, spell_idx, spell_start, year, month, spell_len, region_wkt, threshold
            )
        spell_len = 0
        spell_start = None

    if spell_len >= min_consecutive_months and spell_start:
        _append_spell(
            events, spell_idx, spell_start, last_year, last_month, spell_len, region_wkt, threshold
        )

    logger.info("Detected %d regional drought spells via SPI", len(events))
    return events
