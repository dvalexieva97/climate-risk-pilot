# Europe Climate Risk Assessment

Fine-resolution **hazard layers** and **historical event counts** for European climate perils, built for scale-out from a country pilot to full Europe.

**V0 implementation:** Portugal (mainland), all four hazards, 250 m grid (EPSG:3035).

Methodological reference: [CLIMAAX handbook](https://handbook.climaax.eu) · Framework: IPCC AR5/AR6 **Risk = Hazard × Exposure × Vulnerability** (hazard-only in V0).

## Hazards (Portugal pilot)

| Hazard | Layer | Historical events stored |
|--------|--------|---------------------------|
| Flood | JRC GloFAS inundation depth @ 100y | EFAS flood events → catalog + per-cell count |
| Wildfire | FWI 90th percentile (Jun–Sep) | EFFIS burnt areas → catalog + per-cell count |
| Drought | SPI-12 vs 1991–2020 | Regional drought spells + **drought months below threshold** raster |
| Landslide | ELSUS v2 susceptibility (0–4) | JRC inventory points → catalog + per-cell count |

## Event history outputs

For each hazard and configured lookback window (default **20 years**):

| Output | Location | Description |
|--------|----------|-------------|
| `*_events_20y.parquet` | `data/events/catalog/` | Vector catalog (GeoParquet): id, dates, geometry, source, intensity |
| `event_count_20y.tif` | `data/events/{hazard}/` | Per-cell count of events intersecting the cell |
| `event_count_20y_cog.tif` | same | Cloud Optimized GeoTIFF for map serving |
| `event_summary_20y.json` | same | Region-level stats (total events, max per cell) |
| `drought_months_below_threshold.tif` | `data/events/drought/` | Months with SPI &lt; threshold (drought only) |

Configure window in `config/pilot_portugal.yaml`:

```yaml
event_history:
  years: 20
  # end_year: 2025  # optional; defaults to current year
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Earth Engine (required for flood, wildfire, drought hazard layers)
earthengine authenticate

# ELSUS v2 (required for landslide) — register at ESDAC, then:
mkdir -p data/raw/elsus
# place ELSUS_v2.tif and set ELSUS_RAW_PATH or config path

# Optional: JRC landslide inventory for event counts
mkdir -p data/raw/portugal/landslides
# place inventory.geojson

# NUTS3 boundaries for zonal stats
python scripts/download_nuts3.py

# Run full Portugal pilot
climate-risk run-pilot --config config/pilot_portugal.yaml

# Or use the shell wrapper
bash pipelines/run_portugal.sh
```

### Grid preview

```bash
climate-risk grid-info --config config/pilot_portugal.yaml
```

### GCS upload (uni project)

```bash
export CLIMATE_RISK_GCS_BUCKET=your-bucket
climate-risk run-pilot --config config/pilot_portugal.yaml --upload-gcs
```

See [infra/gcs.md](infra/gcs.md) for bucket layout and titiler setup.

## Project layout

```
config/                 # default + pilot region YAML
src/climate_risk/
  hazards/              # flood, wildfire, drought, landslide processors
  events/               # event schema, catalog I/O, count rasterization
  acquisition/          # EFAS, EFFIS, SPI, landslide inventory fetchers
  aggregate/            # NUTS3 zonal stats
  pipeline/             # orchestration
data/
  reference/            # NUTS3 GeoJSON (generated)
  processed/portugal/   # hazard COGs
  events/portugal/      # event counts + catalog
web/                    # Leaflet map (wire titiler for raster display)
pipelines/run_portugal.sh
infra/gcs.md
```

## Web map

```bash
# After pipeline run + titiler:
pip install titiler.application uvicorn
uvicorn titiler.application.main:app --port 8000

# Edit web/config.js → titilerBase: "http://localhost:8000"
python -m http.server 5500 --directory web
```

Open `http://localhost:5500`.

## Scaling to full Europe

1. Add `config/pilot_{country}.yaml` or use `config/pilot_europe_overview.yaml` (1 km scaffold).
2. Reuse the same processors; only bbox and paths change.
3. Export fine grids per country/basin; keep a coarse Europe overview COG set.
4. Do **not** run 250 m full-Europe until pilot validation passes.

## Caveats (document in any report)

- **ELSUS** is susceptibility, not timed hazard probability.
- **JRC flood** excludes basins &lt; 150 km², no levees/dams.
- **Drought events** in V0 include regional SPI spells; per-cell month counts are in the auxiliary raster.
- Layers use **different units** — no combined “risk score” in V0.

## Licenses

- JRC GloFAS flood: CC BY 4.0  
- ELSUS: ESDAC terms (registration required)  
- EFFIS / EFAS: Copernicus EMS terms  
- ERA5-Land: Copernicus CDS terms  
