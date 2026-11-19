// Entry point: loads the data, fills the banner and footer, and connects the map, the list
// and the details panel so that choosing an area in one updates the others.

import { loadAll } from "./data.js";
import { daysBetween, formatDate, formatHobartTime } from "./format.js";
import { createList, escapeHtml } from "./list.js";
import { createMap } from "./map.js";
import { hidePanel, showPanel } from "./panel.js";

// If the last successful run is older than this, warn even if status.json doesn't say stale
// (for example if the daily job itself stopped running).
const OLD_AFTER_HOURS = 36;

// Write the "data as of" banner. Turns amber when the data is stale or old.
function renderBanner(el, status) {
  const age = (Date.now() - Date.parse(status.run_utc || status.last_attempt_utc)) / 3600000;
  if (status.stale) {
    el.className = "banner stale";
    el.innerHTML = `<strong>Out of date:</strong> today's update failed, so this is the last good forecast
      (issued ${formatDate(status.issue_date)}). Stale since ${formatHobartTime(status.stale_since)}.`;
    return;
  }
  const chlAge = status.inputs?.chl_latest_date ? daysBetween(status.inputs.chl_latest_date, status.issue_date) : null;
  el.className = age > OLD_AFTER_HOURS ? "banner stale" : "banner";
  el.innerHTML = `${age > OLD_AFTER_HOURS ? "<strong>May be out of date.</strong> " : ""}
    Forecast issued <strong>${formatDate(status.issue_date)}</strong> for
    ${formatDate(status.valid_from, false)} – ${formatDate(status.valid_to)} ·
    satellite chlorophyll up to ${formatDate(status.inputs?.chl_latest_date, false)}${chlAge != null ? ` (${chlAge} days before issue)` : ""} ·
    updated ${formatHobartTime(status.run_utc)}`;
}

// Write the data-source credits in the footer, from status.json's attribution list.
function renderAttribution(el, status) {
  const parts = (status.attribution || []).map((a) => {
    const link = a.url || (a.dois && a.dois[0]);
    return link ? `<a href="${escapeHtml(link)}" rel="noopener">${escapeHtml(a.text)}</a>` : escapeHtml(a.text);
  });
  parts.push('Basemap © <a href="https://openfreemap.org" rel="noopener">OpenFreeMap</a>, © <a href="https://www.openstreetmap.org/copyright" rel="noopener">OpenStreetMap</a> contributors');
  el.innerHTML = parts.join(" · ");
}

// Draw the legend for the chosen background layer (colour bar, range, date, caveat).
function renderLegend(el, layers, kind) {
  if (kind === "none") { el.innerHTML = ""; return; }
  const info = layers[kind]?.tas || layers[kind]?.sa;
  if (!info) { el.innerHTML = `<p class="legend-note">This layer is not available today.</p>`; return; }
  const { stops, range, unit, scale } = info.legend;
  const date = info.date ? formatDate(info.date, false) : `${formatDate(info.first_date, false)} – ${formatDate(info.last_date, false)}`;
  const ends = kind === "sst_anomaly"
    ? [`${range[0]} °C colder`, "average", `+${range[1]} °C warmer`]
    : [`${range[0]} ${unit}`, scale === "log" ? "log scale" : "", `${range[1]} ${unit}`];
  el.innerHTML = `
    <div class="legend-bar" style="background: linear-gradient(to right, ${stops.join(", ")})" role="img"
      aria-label="Colour scale from ${ends[0]} to ${ends[2]}"></div>
    <div class="legend-ends"><span>${ends[0]}</span><span>${ends[1]}</span><span>${ends[2]}</span></div>
    <p class="legend-note">${escapeHtml(date)}. ${escapeHtml(info.description || "")}</p>`;
}

// Start the page.
async function start() {
  const banner = document.getElementById("status-banner");
  let data;
  try {
    data = await loadAll();
  } catch (err) {
    banner.className = "banner error";
    banner.textContent = "The forecast data could not be loaded. Please try again later.";
    console.error(err);
    return;
  }
  const { status, areas, layers } = data;
  renderBanner(banner, status);
  renderAttribution(document.getElementById("attribution"), status);

  const byId = new Map(areas.features.map((f) => [f.properties.area_id, f]));
  const panelEl = document.getElementById("panel");

  // Choosing an area (from the map or the list) highlights it everywhere and opens its panel.
  function select(areaId, source) {
    const feature = byId.get(areaId);
    if (!feature) return;
    mapApi.highlight(areaId);
    markSelected(areaId);
    if (source === "list") mapApi.flyTo(feature);
    showPanel(panelEl, feature, status, closePanel, true);
    // On phones the panel sits below the map, so scroll to it; on wider screens just show the
    // top of the sidebar (scrolling the whole page would hide the banner).
    if (window.matchMedia("(max-width: 800px)").matches) panelEl.scrollIntoView({ block: "start" });
    else document.querySelector(".sidebar").scrollTop = 0;
  }

  // Closing the panel clears the selection and returns focus to the list.
  function closePanel() {
    hidePanel(panelEl);
    mapApi.highlight(null);
    markSelected(null);
    document.getElementById("area-list-heading").focus();
  }

  const mapApi = createMap({ container: "map", areas, layers, onSelect: select });
  const markSelected = createList({
    features: areas.features,
    listEl: document.getElementById("area-items"),
    searchEl: document.getElementById("area-search"),
    countEl: document.getElementById("area-count"),
    onSelect: select,
  });

  // Background layer radio buttons.
  const legendEl = document.getElementById("layer-legend");
  document.getElementById("layer-control").addEventListener("change", (e) => {
    if (e.target.name !== "layer") return;
    mapApi.showLayer(e.target.value);
    renderLegend(legendEl, layers, e.target.value);
  });

  // Escape closes the panel.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panelEl.hidden) closePanel();
  });
}

start();
