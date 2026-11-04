# Historical event storage

Each hazard pipeline produces **three tiers** of event-history data for the configured lookback window (`event_history.years`, default 20).

## 1. Vector catalog (GeoParquet)

Path: `data/events/catalog/{hazard}_events_{N}y.parquet`

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | string | Stable identifier |
| `hazard` | string | `flood`, `wildfire`, `drought`, `landslide` |
| `start_date` | date | Event start (ISO) |
| `end_date` | date | Event end (ISO) |
| `geometry` | geometry | Footprint or point (WGS84) |
| `source` | string | e.g. EFFIS, EFAS, JRC inventory |
| `intensity` | float | Optional (depth, area ha, SPI, class) |
| `intensity_unit` | string | Optional |
| `metadata` | object | Source-specific fields |

Use this for tables, timelines, and validation against known disasters.

## 2. Per-cell event count raster

Path: `data/events/{hazard}/event_count_{N}y.tif` (+ `_cog.tif`)

Each cell stores the **number of catalog events** whose geometry intersects that cell (250 m grid, EPSG:3035).

- Wildfire: one count per burnt-area polygon intersecting the cell  
- Flood: one count per EFAS flood event polygon  
- Landslide: one count per inventory point/polygon  
- Drought: one count per **regional drought spell** (polygon); see tier 3 for finer metric  

## 3. Hazard-specific auxiliary rasters

| Hazard | Extra raster | Meaning |
|--------|----------------|---------|
| Drought | `drought_months_below_threshold.tif` | Number of months in the lookback window where SPI &lt; threshold |

Future additions (Europe scale):

- Wildfire: `burned_area_ha_cumulative.tif`  
- Flood: `max_depth_observed.tif` from event catalog where depth available  

## Summary JSON

`data/events/{hazard}/event_summary_{N}y.json` — region totals:

```json
{
  "event_count": 142,
  "cells_with_events": 891,
  "max_events_per_cell": 7
}
```

## NUTS3 aggregation

`data/processed/portugal/nuts3/hazard_summary.parquet` includes:

- `{hazard}_mean`, `{hazard}_max`, `{hazard}_p90` — hazard layer zonal stats  
- `{hazard}_events_sum` — total event counts summed over each NUTS3 unit  

## Changing the lookback window

Edit `config/pilot_portugal.yaml`:

```yaml
event_history:
  years: 30
  end_year: 2024
```

Re-run `climate-risk run-pilot`. Output filenames include `{N}y` to avoid overwriting.
