# GCS layout for climate-risk outputs

## Bucket structure

```
gs://{CLIMATE_RISK_GCS_BUCKET}/climate-risk/v0/portugal/
├── processed/
│   ├── flood/flood_depth_100y_cog.tif
│   ├── wildfire/fwi_p90_summer_cog.tif
│   ├── drought/spi12_mean_cog.tif
│   ├── landslide/elsus_susceptibility_cog.tif
│   ├── nuts3/hazard_summary.parquet
│   └── manifest.json
└── events/
    ├── catalog/
    │   ├── flood_events_20y.parquet
    │   ├── wildfire_events_20y.parquet
    │   ├── drought_events_20y.parquet
    │   └── landslide_events_20y.parquet
    ├── flood/event_count_20y_cog.tif
    ├── wildfire/event_count_20y_cog.tif
    ├── drought/
    │   ├── event_count_20y_cog.tif
    │   └── drought_months_below_threshold.tif
    └── landslide/event_count_20y_cog.tif
```

## Setup (uni GCP)

1. Create or reuse a bucket in your uni project (region: `europe-west1` or similar).
2. Grant your user/service account `storage.objectAdmin` on the bucket.
3. Set environment variables (see `.env.example`):

   ```bash
   export CLIMATE_RISK_GCS_BUCKET=your-bucket
   export CLIMATE_RISK_GCS_UPLOAD=true
   ```

4. Run with upload:

   ```bash
   climate-risk run-pilot --config config/pilot_portugal.yaml --upload-gcs
   ```

## Serving COGs to the web map

**Option A — titiler (recommended for dev)**

```bash
pip install titiler.application uvicorn
uvicorn titiler.application.main:app --port 8000
```

Set `web/config.js` → `titilerBase: "http://localhost:8000"`.

**Option B — public bucket + Cloud CDN**

Make pilot COGs public-read (or signed URLs) and point titiler at `gs://` URLs.

## Cost notes

- Store only harmonized COGs + event layers; do not keep duplicate raw downloads.
- Use Nearline/Coldline for Europe-wide archive after validation.
- Earth Engine exports avoid multi-GB JRC FTP downloads when datasets are in the EE catalog.
