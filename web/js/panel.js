// The details panel for one selected harvest area: tier, probability, the evidence behind it,
// sea-temperature context, the official status, the disclaimer and two 90-day charts.

import { drawCharts } from "./chart.js";
import { loadSeries } from "./data.js";
import { TIER_LETTERS, evidenceSentence, formatDate, formatPercent, ratioText } from "./format.js";
import { escapeHtml } from "./list.js";

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

    <p class="tier-line">
      <span class="tier-dot tier-${p.tier}" aria-hidden="true">${TIER_LETTERS[p.tier]}</span>
      <span><strong>${p.tier} risk</strong> · ${formatPercent(p.probability)} chance of an unusually green week</span>
    </p>
    <p class="note">For ${formatDate(p.valid_from, false)} – ${formatDate(p.valid_to)} (issued ${formatDate(p.issue_date, false)}).</p>
    ${p.stale_chl ? `<p class="warn">No clear satellite view in the last 14 days: this is the usual risk for the time of year, not a current reading.</p>` : ""}

    <h3>Why</h3>
    <p>${escapeHtml(evidenceSentence(ev))}</p>
    <dl>
      <dt>Last 7 days</dt><dd>${ratioText(ev.recent7_log10_anomaly)} normal</dd>
      <dt>7 days before</dt><dd>${ratioText(ev.prior7_log10_anomaly)} normal</dd>
      <dt>Clear views</dt><dd>${ev.clear_days_of_14 ?? 0} of the last 14 days${ev.last_clear_date ? `, latest ${formatDate(ev.last_clear_date, false)}` : ""}</dd>
      <dt>Sea temperature</dt><dd>${ctx.sst_anomaly_c == null ? "n/a" : `${ctx.sst_anomaly_c > 0 ? "+" : ""}${ctx.sst_anomaly_c.toFixed(1)} °C vs 1991–2020 average`}</dd>
    </dl>
    <p class="note">The forecast uses satellite chlorophyll only. Sea temperature is shown for context and is not used.</p>

    <h3>Official status</h3>
    <p>${off.status ? `<strong>${escapeHtml(off.status.replace("_", " ").toLowerCase())}</strong> in the ShellMAP notice archived ${formatDate(off.snapshot_date, false)}.` : "Not found in our archive of ShellMAP notices."}
      <a href="${escapeHtml(off.url || "https://nre.tas.gov.au/aquaculture/shellmap/growing-and-harvest-areas")}" rel="noopener">Check the current official status</a>.</p>

    <div class="chart" id="panel-charts"><p class="note">Loading the 90-day history…</p></div>

    <p class="disclaimer-box"><strong>Experimental research tool.</strong> ${escapeHtml((p.disclaimer || "").replace(/^Experimental research tool\.\s*/, ""))}</p>
    <p class="note">${escapeHtml(p.geometry_note || "")}</p>`;
  panelEl.hidden = false;
  panelEl.querySelector(".close-btn").addEventListener("click", onClose);
  if (moveFocus) panelEl.focus();

  // Load and draw the charts after the text is visible (they need one extra small download).
  const chartsEl = panelEl.querySelector("#panel-charts");
  loadSeries(p.timeseries)
    .then((series) => drawCharts(chartsEl, series, status.tier_cutoffs))
    .catch(() => { chartsEl.innerHTML = `<p class="note">The 90-day history could not be loaded.</p>`; });
}

// Hide and empty the panel.
export function hidePanel(panelEl) {
  panelEl.hidden = true;
  panelEl.innerHTML = "";
}
