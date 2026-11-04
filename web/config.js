/* Map tile URLs — point to local COGs via titiler, or GCS public/signed URLs */

window.CLIMATE_RISK_MAP_CONFIG = {
  region: "portugal",
  bbox: [-9.53, 36.84, -6.19, 42.16],
  eventHistoryYears: 20,
  // Local titiler example: http://localhost:8000/cog/tiles/WebMercatorQuad/{z}/{x}/{y}?url=...
  titilerBase: "", // set when running titiler against processed COGs
  layers: {
    flood: {
      label: "Flood depth (100y)",
      path: "../data/processed/portugal/flood/flood_depth_100y_cog.tif",
      unit: "m",
      eventCountPath: "../data/events/portugal/flood/event_count_20y_cog.tif",
    },
    wildfire: {
      label: "FWI p90 (Jun–Sep)",
      path: "../data/processed/portugal/wildfire/fwi_p90_summer_cog.tif",
      unit: "index",
      eventCountPath: "../data/events/portugal/wildfire/event_count_20y_cog.tif",
    },
    drought: {
      label: "SPI-12 mean",
      path: "../data/processed/portugal/drought/spi12_mean_cog.tif",
      unit: "SPI",
      eventCountPath: "../data/events/portugal/drought/event_count_20y_cog.tif",
    },
    landslide: {
      label: "ELSUS susceptibility",
      path: "../data/processed/portugal/landslide/elsus_susceptibility_cog.tif",
      unit: "class 0–4",
      eventCountPath: "../data/events/portugal/landslide/event_count_20y_cog.tif",
    },
  },
};
