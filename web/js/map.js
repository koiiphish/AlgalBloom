// The map: basemap, the two satellite image layers, and one marker per harvest area.
// Uses MapLibre GL JS (vendored in web/vendor, BSD-3 licence).

import * as maplibregl from "../vendor/maplibre-gl-6.19.0/maplibre-gl.mjs";
import { TIER_COLOURS, TIER_LETTERS } from "./format.js";

// Free, keyless basemap (design note D004): OpenFreeMap's muted "positron" style, so the
// coloured markers and satellite layers stand out. MapLibre shows its attribution.
const BASEMAP_URL = "https://tiles.openfreemap.org/styles/positron";

// Positron draws the sea grey, which would hide the grey "Low" markers; tint it pale blue.
const SEA_COLOUR = "#c9dcea";

// If the basemap hasn't loaded after this long, switch to a plain background (D004 risk:
// OpenFreeMap has no service guarantee). Our own data still shows on top.
const BASEMAP_TIMEOUT_MS = 10000;

// A minimal style with no external tiles: just a sea-coloured background.
const FALLBACK_STYLE = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": SEA_COLOUR } }],
};

// Start view: Tasmania and South Australia together.
const START_BOUNDS = [[131.5, -44.0], [149.0, -31.8]];

// Create the map and keep our data layers on it, even if the basemap has to be swapped for
// the fallback. Returns a small object with functions the rest of the page uses.
export function createMap({ container, areas, layers, onSelect }) {
  const map = new maplibregl.Map({
    container,
    style: BASEMAP_URL,
    bounds: START_BOUNDS,
    fitBoundsOptions: { padding: 20 },
    attributionControl: { compact: true },
    cooperativeGestures: false,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
  // Fit the start view again once the page layout has settled (the map's container can still
  // be changing size while the map is created).
  map.once("load", () => { map.resize(); map.fitBounds(START_BOUNDS, { padding: 20, animate: false }); });

  let activeLayer = "none";
  let selectedId = null;
  let usingFallback = false;

  // Switch to the plain fallback background (only once).
  function useFallback(reason) {
    if (usingFallback) return;
    usingFallback = true;
    console.warn("Basemap unavailable, using plain background:", reason);
    map.setStyle(FALLBACK_STYLE);
    document.getElementById("map").dataset.fallback = "true";
  }
  const timer = setTimeout(() => {
    if (!map.isStyleLoaded()) useFallback("timeout");
  }, BASEMAP_TIMEOUT_MS);
  map.on("error", (e) => {
    // Errors while fetching the basemap style itself (not individual tiles) trigger the fallback.
    if (!map.isStyleLoaded() && String(e?.error?.message || "").includes("style")) useFallback(e.error.message);
  });

  // Every time a style finishes loading (the basemap, or the fallback), add our layers again.
  map.on("style.load", () => {
    clearTimeout(timer);
    if (map.getLayer("water")) map.setPaintProperty("water", "fill-color", SEA_COLOUR);
    addRasterLayers();
    addAreaLayers();
    showLayer(activeLayer);
    highlight(selectedId);
  });

  // Find the first label layer of the basemap, so our images go under the place names.
  function firstLabelLayer() {
    const layer = map.getStyle().layers.find((l) => l.type === "symbol");
    return layer ? layer.id : undefined;
  }

  // Add each satellite image (chlorophyll, SST anomaly; SA and Tasmania) as a hidden layer.
  function addRasterLayers() {
    for (const kind of ["chl", "sst_anomaly"]) {
      for (const [region, info] of Object.entries(layers[kind] || {})) {
        const id = `${kind}-${region}`;
        if (map.getSource(id)) continue;
        map.addSource(id, { type: "image", url: `rasters/${info.file}`, coordinates: info.coordinates });
        map.addLayer(
          {
            id, type: "raster", source: id,
            layout: { visibility: "none" },
            paint: { "raster-opacity": 0.85, "raster-resampling": kind === "chl" ? "nearest" : "linear" },
          },
          firstLabelLayer(),
        );
      }
    }
  }

  // Add the harvest-area markers: a coloured circle plus the tier letter, larger for higher
  // risk, with a dark outline so the amber shows up against the blue sea.
  function addAreaLayers() {
    if (map.getSource("areas")) return;
    // MapLibre only needs a few flat properties for styling; full details stay in JavaScript.
    const slim = {
      type: "FeatureCollection",
      features: areas.features.map((f) => ({
        type: "Feature",
        geometry: f.geometry,
        properties: { area_id: f.properties.area_id, tier: f.properties.tier, letter: TIER_LETTERS[f.properties.tier] },
      })),
    };
    map.addSource("areas", { type: "geojson", data: slim, promoteId: "area_id" });
    const tierColour = ["match", ["get", "tier"], "High", TIER_COLOURS.High, "Moderate", TIER_COLOURS.Moderate, TIER_COLOURS.Low];
    map.addLayer({
      id: "areas-circle", type: "circle", source: "areas",
      paint: {
        "circle-color": tierColour,
        // Small dots when zoomed out (areas crowd together), full size from zoom 8.
        "circle-radius": ["interpolate", ["linear"], ["zoom"],
          5, ["match", ["get", "tier"], "High", 5, "Moderate", 4.5, 4],
          8, ["match", ["get", "tier"], "High", 10, "Moderate", 9, 8]],
        "circle-stroke-color": ["case", ["boolean", ["feature-state", "selected"], false], "#0e6e8c", "#1a1a19"],
        "circle-stroke-width": ["case", ["boolean", ["feature-state", "selected"], false], 4, 1.2],
      },
    });
    // Letters need the basemap's fonts, so they are skipped on the plain fallback style.
    if (!usingFallback) {
      map.addLayer({
        id: "areas-letter", type: "symbol", source: "areas",
        minzoom: 7, // letters appear once markers are big enough to hold them
        layout: {
          "text-field": ["get", "letter"], "text-font": ["Noto Sans Bold"], "text-size": 11,
          "text-allow-overlap": true, "text-ignore-placement": true,
        },
        paint: { "text-color": ["match", ["get", "tier"], "Moderate", "#1a1a19", "#ffffff"] },
      });
    }
  }

  // Clicking a marker selects that area; the pointer changes over markers.
  map.on("click", "areas-circle", (e) => onSelect(e.features[0].properties.area_id, "map"));
  map.on("mouseenter", "areas-circle", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "areas-circle", () => { map.getCanvas().style.cursor = ""; });

  // Show one background image layer ("chl", "sst_anomaly" or "none") for both regions.
  function showLayer(kind) {
    activeLayer = kind;
    for (const k of ["chl", "sst_anomaly"]) {
      for (const region of Object.keys(layers[k] || {})) {
        const id = `${k}-${region}`;
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", k === kind ? "visible" : "none");
      }
    }
  }

  // Draw a blue ring around the selected area (and remove it from the previous one).
  function highlight(areaId) {
    if (!map.getSource("areas")) { selectedId = areaId; return; }
    if (selectedId) map.setFeatureState({ source: "areas", id: selectedId }, { selected: false });
    selectedId = areaId;
    if (areaId) map.setFeatureState({ source: "areas", id: areaId }, { selected: true });
  }

  // Move the map to an area (used when it's picked from the list).
  function flyTo(feature) {
    map.flyTo({ center: feature.geometry.coordinates, zoom: Math.max(map.getZoom(), 9), essential: true });
  }

  return { map, showLayer, highlight, flyTo };
}
