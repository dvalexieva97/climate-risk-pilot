const cfg = window.CLIMATE_RISK_MAP_CONFIG;

const map = L.map("map", { zoomControl: true }).setView([39.5, -8.0], 7);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
  maxZoom: 18,
}).addTo(map);

map.fitBounds([
  [cfg.bbox[1], cfg.bbox[0]],
  [cfg.bbox[3], cfg.bbox[2]],
]);

document.getElementById("event-years").textContent = cfg.eventHistoryYears;

let hazardOverlay = null;
let eventOverlay = null;

function layerUrl(localPath) {
  if (cfg.titilerBase) {
    const encoded = encodeURIComponent(new URL(localPath, window.location.href).href);
    return `${cfg.titilerBase}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}?url=${encoded}`;
  }
  return null;
}

function updateLegend(layerKey) {
  const layer = cfg.layers[layerKey];
  document.getElementById("legend-body").innerHTML = `
    <strong>${layer.label}</strong><br/>
    Unit: ${layer.unit}<br/>
    <em>Run titiler or set GCS tile URL to render rasters in-browser.</em>
  `;
}

function setHazardLayer(layerKey) {
  if (hazardOverlay) map.removeLayer(hazardOverlay);
  const layer = cfg.layers[layerKey];
  const url = layerUrl(layer.path);
  if (url) {
    hazardOverlay = L.tileLayer(url, { opacity: 0.75 }).addTo(map);
  }
  updateLegend(layerKey);
}

function toggleEventLayer(show) {
  if (eventOverlay) {
    map.removeLayer(eventOverlay);
    eventOverlay = null;
  }
  if (!show) return;
  const layerKey = document.querySelector('input[name="layer"]:checked').value;
  const layer = cfg.layers[layerKey];
  const url = layerUrl(layer.eventCountPath);
  if (url) {
    eventOverlay = L.tileLayer(url, { opacity: 0.55 }).addTo(map);
  }
}

document.querySelectorAll('input[name="layer"]').forEach((el) => {
  el.addEventListener("change", (e) => setHazardLayer(e.target.value));
});

document.getElementById("show-events").addEventListener("change", (e) => {
  toggleEventLayer(e.target.checked);
});

map.on("click", (e) => {
  document.getElementById("info-body").textContent =
    `Lat/lon: ${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}\n` +
    `(Point query requires titiler /stats endpoint or precomputed sample.)`;
});

// Portugal outline for context when rasters not yet served
L.rectangle(
  [
    [cfg.bbox[1], cfg.bbox[0]],
    [cfg.bbox[3], cfg.bbox[2]],
  ],
  { color: "#2563eb", weight: 2, fillOpacity: 0.02 }
).addTo(map);

setHazardLayer("flood");
