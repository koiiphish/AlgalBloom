// The details panel for one selected harvest area, in two layers:
//   1. a short summary that fits on one screen: tier, the three key facts, a small 90-day
//      risk chart and a one-line disclaimer
//   2. "More info" (a native <details> section the reader opens if they want): why this
//      rating, what the area covers, full charts, sea temperature, official status, caveats.

import { drawCharts, drawSparkline } from "./chart.js";
import { loadSeries } from "./data.js";
import { TIER_LETTERS, evidenceSentence, formatDate, formatPercent, ratioText } from "./format.js";
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
const TREND = { rising: "↑ rising", falling: "↓ falling", steady: "→ steady", unknown: "" };

// Official status in plain words, e.g. "OPEN_CONDITIONAL" -> "Open (conditional)".
function statusWords(status) {
  if (!status) return "Not in our archive";
  const words = { OPEN: "Open", CLOSED: "Closed", PROHIBITED: "Prohibited", OPEN_CONDITIONAL: "Open (conditional)" };
  return words[status] ?? status.replace(/_/g, " ").toLowerCase();
}

// The short summary block (always visible).
function summaryHtml(p, ev, off) {
  const trend = TREND[ev.trend] || "";
  return `
    <div class="tier-band tier-band-${p.tier}">
      <span class="tier-dot tier-${p.tier}" aria-hidden="true">${TIER_LETTERS[p.tier]}</span>
      <div>
        <p class="tier-band-title">${p.tier} risk · ${formatPercent(p.probability)}</p>
        <p class="tier-band-sub">Chance of an unusually green week, ${formatDate(p.valid_from, false)} – ${formatDate(p.valid_to, false)}</p>
      </div>
    </div>
    ${p.stale_chl ? `<p class="warn">No clear satellite view for 14 days: showing the usual risk for this time of year.</p>` : ""}
    <dl class="facts">
      <dt>Chlorophyll</dt><dd>${ev.score_log10_anomaly == null ? "no clear view" : `<strong>${ratioText(ev.score_log10_anomaly)}</strong> normal`} ${trend ? `<span class="trend">${trend}</span>` : ""}</dd>
      <dt>Clear views</dt><dd>${ev.clear_days_of_14 ?? 0} of the last 14 days</dd>
      <dt>Official status</dt><dd>${escapeHtml(statusWords(off.status))}</dd>
    </dl>
    <p class="mini-chart-title">Risk, last 90 days</p>
    <div class="mini-chart" id="panel-spark"></div>
    <p class="one-line-disclaimer">⚠ Experimental. <a href="${escapeHtml(off.url || SHELLMAP_PAGE)}" rel="noopener">Check the official status</a> before harvesting.</p>`;
}

// The "More info" section (closed until the reader opens it).
function moreInfoHtml(p, ev, ctx, off) {
  return `
    <details class="more-info">
      <summary>More info</summary>

      <h3>Why this rating</h3>
      <p>${escapeHtml(evidenceSentence(ev))}</p>
      <dl class="facts">
        <dt>Last 7 days</dt><dd>${ratioText(ev.recent7_log10_anomaly)} normal</dd>
        <dt>7 days before</dt><dd>${ratioText(ev.prior7_log10_anomaly)} normal</dd>
        <dt>Latest clear view</dt><dd>${ev.last_clear_date ? formatDate(ev.last_clear_date, false) : "none in 14 days"}</dd>
      </dl>

      <h3>What this area covers</h3>
      <p>ShellMAP harvest area <strong>${escapeHtml(p.harvest_area)}</strong> in the ${escapeHtml(p.growing_area)} growing area, plus the water within 2 km of it.
        The map shows a point because the official boundaries can't be published yet.</p>

      <h3>Last 90 days</h3>
      <div class="chart" id="panel-charts"><p class="note">Loading…</p></div>

      <h3>Sea temperature</h3>
      <p>${ctx.sst_anomaly_c == null ? "Not available today." : `${ctx.sst_anomaly_c > 0 ? "+" : ""}${ctx.sst_anomaly_c.toFixed(1)} °C compared with the 1991–2020 average.`}
        <span class="note">Shown for context only; the forecast doesn't use it.</span></p>

      <h3>Official status</h3>
      <p><strong>${escapeHtml(statusWords(off.status))}</strong>${off.snapshot_date ? ` in the ShellMAP notice of ${formatDate(off.snapshot_date, false)}` : ""}${off.since ? `, since ${formatDate(off.since.slice(0, 10))}` : ""}.
        <a href="${escapeHtml(off.url || SHELLMAP_PAGE)}" rel="noopener">Current official notice</a></p>

      <h3>Keep in mind</h3>
      <ul class="caveats">
        <li>Chlorophyll is a proxy: some toxic algae cause problems without raising it. Low does not mean safe.</li>
        <li>The forecast reacts to recent conditions; it can't see a bloom before it starts.</li>
        <li>Inshore satellite readings can be raised by sediment and tannins after rain.</li>
      </ul>
      <p class="disclaimer-box"><strong>Experimental research tool.</strong> ${escapeHtml((p.disclaimer || "").replace(/^Experimental research tool\.\s*/, ""))}
        <a href="about.html">How it works</a></p>
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
