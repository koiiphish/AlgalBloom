// Loads the pre-computed files the daily GitHub Action publishes next to this page:
//   status.json (freshness), areas.geojson (forecasts), layers.json (map images),
//   timeseries/<area>.json (90-day history of one area, loaded only when it's opened).
// The site is static, so "loading data" just means fetching these files.

// Fetch one JSON file. A "?v=" tag makes the browser get today's copy rather than an old
// cached one; it changes every hour, so repeat visits within an hour still use the cache.
async function getJson(path) {
  const hourTag = new Date().toISOString().slice(0, 13);
  const response = await fetch(`${path}?v=${hourTag}`);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

// Load everything the map needs at start-up, in parallel.
// areas.geojson and layers.json may be missing (e.g. on the very first failed run), so those
// two fall back to empty values instead of stopping the page.
export async function loadAll() {
  const [status, areas, layers] = await Promise.all([
    getJson("status.json"),
    getJson("areas.geojson").catch(() => ({ type: "FeatureCollection", features: [] })),
    getJson("layers.json").catch(() => ({ chl: {}, sst_anomaly: {} })),
  ]);
  return { status, areas, layers };
}

// Load one area's 90-day time series (path comes from the area's "timeseries" property).
// Results are remembered, so re-opening an area doesn't download it again.
const seriesCache = new Map();
export async function loadSeries(path) {
  if (!seriesCache.has(path)) {
    // Forget a failed download, so the next click tries again.
    const request = getJson(path).catch((err) => {
      seriesCache.delete(path);
      throw err;
    });
    seriesCache.set(path, request);
  }
  return seriesCache.get(path);
}
