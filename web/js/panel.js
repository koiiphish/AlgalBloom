// The details panel for one selected harvest area, in two layers:
//   1. a short summary that fits on one screen: tier, the three key facts, a small 90-day
//      risk chart and a one-line disclaimer
//   2. "More info" (a native <details> section the reader opens if they want): why this
//      rating, what the area covers, full charts, sea temperature, official status, caveats.

import { drawCharts, drawSparkline } from "./chart.js";
import { loadSeries } from "./data.js";
import { TIER_LETTERS, evidenceSentence, formatPercent, formatRange, formatShortDate, ratioText } from "./format.js";
import { escapeHtml } from "./list.js";

// Fallback official link if an area has none (verified in docs/data_sources.md).
const SHELLMAP_PAGE = "https://nre.tas.gov.au/aquaculture/shellmap/growing-and-harvest-areas";

// Redraws the open panel's charts at a new width (set by showPanel, used by redrawCharts).
let redrawOpenCharts = null;
let redrawTimer = null;

// Called when the sidebar is resized: redraw the charts once the dragging pauses.
export function redrawCharts() {
  clearTimeout(redrawTimer);
  redrawTimer = setTimeout(() => redrawOpenCharts?.(), 150);
}

// Arrow + word for the chlorophyll trend.
const TREND = { rising: "↑ increasing", falling: "↓ decreasing", steady: "→ stable", unknown: "" };

// ShellMAP status codes as short labels, e.g. "OPEN_CONDITIONAL" -> "Open (conditional)".
function statusWords(status) {
  if (!status) return "Not recorded";
  const words = { OPEN: "Open", CLOSED: "Closed", PROHIBITED: "Prohibited", OPEN_CONDITIONAL: "Open (conditional)" };
  return words[status] ?? status.replace(/_/g, " ").toLowerCase();
}

// Signed SST anomaly, e.g. "+1.6 °C".
function sstText(value) {
  return value == null ? "n/a" : `${value > 0 ? "+" : ""}${value.toFixed(1)} °C`;
}

// The short summary block (always visible).
function summaryHtml(p, ev, off) {
  const trend = TREND[ev.trend] || "";
  return `
    <div class="tier-band tier-band-${p.tier}">
      <span class="tier-dot tier-${p.tier}" aria-hidden="true">${TIER_LETTERS[p.tier]}</span>
      <div>
        <p class="tier-band-title">${p.tier} risk · ${formatPercent(p.probability)}</p>
        <p class="tier-band-sub">Probability of elevated chlorophyll-a, <span class="nowrap">${formatRange(p.valid_from, p.valid_to)}</span></p>
      </div>
    </div>
    ${p.stale_chl ? `<p class="warn">No cloud-free imagery in 14 days. Seasonal baseline risk shown.</p>` : ""}
    <dl class="facts">
      <dt>Chlorophyll-a</dt><dd>${ev.score_log10_anomaly == null ? "n/a" : `<strong>${ratioText(ev.score_log10_anomaly)}</strong> monthly median`} ${trend ? `<span class="trend">${trend}</span>` : ""}</dd>
      <dt>Cloud-free days</dt><dd>${ev.clear_days_of_14 ?? 0} of 14</dd>
      <dt>ShellMAP status</dt><dd>${escapeHtml(statusWords(off.status))}</dd>
    </dl>
    <p class="mini-chart-title">Risk, 90 days</p>
    <div class="mini-chart" id="panel-spark"></div>
    <p class="one-line-disclaimer">Experimental. Refer to <a href="${escapeHtml(off.url || SHELLMAP_PAGE)}" rel="noopener">ShellMAP</a> for harvest status.</p>`;
}

// The "More info" section (closed until the reader opens it).
function moreInfoHtml(p, ev, ctx, off) {
  return `
    <details class="more-info">
      <summary>More info</summary>

      <h3>Basis</h3>
      <p>${escapeHtml(evidenceSentence(ev))}</p>
      <dl class="facts">
        <dt>Recent 7 days</dt><dd>${ratioText(ev.recent7_log10_anomaly)}</dd>
        <dt>Previous 7 days</dt><dd>${ratioText(ev.prior7_log10_anomaly)}</dd>
        <dt>Last cloud-free image</dt><dd>${ev.last_clear_date ? formatShortDate(ev.last_clear_date) : "none"}</dd>
      </dl>
      <p class="note">Relative to the area's 2016–2022 median for the month.</p>

      <h3>Coverage</h3>
      <p>ShellMAP harvest area ${escapeHtml(p.harvest_area)}, ${escapeHtml(p.growing_area)}, and waters within 2 km.
        Shown as a point pending boundary licensing.</p>

      <h3>90-day record</h3>
      <div class="chart" id="panel-charts"><p class="note">Loading…</p></div>

      <h3>Sea surface temperature</h3>
      <p>${sstText(ctx.sst_anomaly_c)} relative to the 1991–2020 mean. Not used in the forecast.</p>

      <h3>ShellMAP status</h3>
      <p>${escapeHtml(statusWords(off.status))}${off.since ? ` since ${formatShortDate(off.since)} ${off.since.slice(0, 4)}` : ""}${off.snapshot_date ? ` (notice archived ${formatShortDate(off.snapshot_date)})` : ""}.
        <a href="${escapeHtml(off.url || SHELLMAP_PAGE)}" rel="noopener">Current notice</a></p>

      <h3>Limitations</h3>
      <ul class="caveats">
        <li>Chlorophyll-a is a proxy. Toxic species can occur at low biomass; Low risk does not indicate safety.</li>
        <li>The forecast responds to observed conditions and does not predict bloom onset.</li>
        <li>Inshore satellite values may be inflated by sediment and dissolved organic matter.</li>
      </ul>
      <p class="disclaimer-box"><strong>Experimental research tool.</strong> ${escapeHtml((p.disclaimer || "").replace(/^Experimental research tool\.\s*/, ""))}
        <a href="about.html">Method</a></p>
    </details>`;
}

// Fill the panel for one area feature and show it. `status` supplies the tier cut-offs.
// `onClose` is called when the user closes the panel.
export function showPanel(panelEl, feature, status, onClose, moveFocus) {
  const p = feature.properties;
  const ev = p.evidence || {};
  const ctx = p.context || {};
  const off = p.official || {};
  panelEl.innerHTML = `
    <div class="panel-head">
      <div>
        <h2 id="panel-title">${escapeHtml(p.harvest_area)}</h2>
        <p class="sub">${escapeHtml(p.growing_area)}, Tasmania</p>
      </div>
      <button type="button" class="close-btn" aria-label="Close area details">Close</button>
    </div>
    ${summaryHtml(p, ev, off)}
    ${moreInfoHtml(p, ev, ctx, off)}`;
  panelEl.hidden = false;
  panelEl.querySelector(".close-btn").addEventListener("click", onClose);
  if (moveFocus) panelEl.focus();

  // Load the 90-day history once, then draw the small summary chart now and the full charts
  // the first time "More info" is opened (they need the panel's width to be known).
  const sparkEl = panelEl.querySelector("#panel-spark");
  const chartsEl = panelEl.querySelector("#panel-charts");
  const details = panelEl.querySelector(".more-info");
  const seriesPromise = loadSeries(p.timeseries);
  seriesPromise
    .then((series) => drawSparkline(sparkEl, series, status.tier_cutoffs))
    .catch(() => { sparkEl.innerHTML = `<p class="note">History not available.</p>`; });
  redrawOpenCharts = () => seriesPromise.then((series) => {
    drawSparkline(sparkEl, series, status.tier_cutoffs);
    if (chartsEl.dataset.drawn) drawCharts(chartsEl, series, status.tier_cutoffs);
  }).catch(() => {});
  details.addEventListener("toggle", () => {
    if (!details.open || chartsEl.dataset.drawn) return;
    chartsEl.dataset.drawn = "true";
    seriesPromise
      .then((series) => drawCharts(chartsEl, series, status.tier_cutoffs))
      .catch(() => { chartsEl.innerHTML = `<p class="note">The 90-day history could not be loaded.</p>`; });
  });
}

// Hide and empty the panel.
export function hidePanel(panelEl) {
  redrawOpenCharts = null;
  panelEl.hidden = true;
  panelEl.innerHTML = "";
}
