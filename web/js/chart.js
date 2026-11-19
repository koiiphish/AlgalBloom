// The two small 90-day charts in an area's panel, drawn with uPlot (vendored, MIT licence):
//   1. forecast probability, with the Moderate and High cut-offs as dashed lines
//   2. chlorophyll compared with normal ("× normal", log scale) on clear-sky days
// Two separate charts on purpose: they measure different things, so they never share an axis.
// uPlot shows the values under the cursor in the legend row (the hover read-out).

import uPlot from "../vendor/uplot-1.6.32/uPlot.esm.js";
import { TIER_COLOURS } from "./format.js";

// Convert "2026-11-19" dates into the seconds-since-1970 numbers uPlot uses for its x axis.
function toUnixSeconds(dates) {
  return dates.map((d) => Date.parse(`${d}T00:00:00Z`) / 1000);
}

// Draw horizontal dashed reference lines, e.g. the tier cut-offs. `lines` is a list of
// {value, colour}. (A uPlot "hook" is a function uPlot calls after drawing the chart.)
function referenceLines(lines) {
  return (u) => {
    const ctx = u.ctx;
    for (const { value, colour } of lines) {
      if (value == null) continue;
      const y = Math.round(u.valToPos(value, "y", true));
      ctx.save();
      ctx.strokeStyle = colour;
      ctx.lineWidth = 1.5 * devicePixelRatio;
      ctx.setLineDash([5 * devicePixelRatio, 4 * devicePixelRatio]);
      ctx.beginPath();
      ctx.moveTo(u.bbox.left, y);
      ctx.lineTo(u.bbox.left + u.bbox.width, y);
      ctx.stroke();
      ctx.restore();
    }
  };
}

// Shared look for both charts: thin lines, quiet grid, dates on the x axis.
function baseOptions(width, title) {
  return {
    width, height: 150, title,
    cursor: { drag: { x: false, y: false } },
    scales: { x: { time: true } },
    axes: [
      { stroke: "#4b5563", grid: { stroke: "#eef2f5" }, ticks: { stroke: "#dde4ea" }, font: "12px Inter, system-ui, sans-serif" },
      { stroke: "#4b5563", grid: { stroke: "#eef2f5" }, ticks: { stroke: "#dde4ea" }, size: 48, font: "12px Inter, system-ui, sans-serif" },
    ],
  };
}

// A small risk chart for the panel summary: the 90-day probability line with the Moderate
// and High cut-offs dashed. No legend; hovering shows the date and value in a single line.
export function drawSparkline(container, series, cutoffs) {
  container.innerHTML = "";
  const width = Math.max(240, container.clientWidth || 320);
  const opts = baseOptions(width);
  opts.height = 110;
  opts.legend = { show: false };
  opts.scales.y = { range: [0, 1] };
  opts.axes[1].size = 50;
  opts.axes[1].values = (u, ticks) => ticks.map((t) => `${Math.round(t * 100)}%`);
  opts.axes[1].splits = () => [0, 0.5, 1];
  opts.series = [{}, { label: "Probability", stroke: "#0e6e8c", width: 2 }];
  opts.hooks = { draw: [referenceLines([
    { value: cutoffs?.moderate, colour: TIER_COLOURS.Moderate },
    { value: cutoffs?.high, colour: TIER_COLOURS.High },
  ])] };
  new uPlot(opts, [toUnixSeconds(series.dates), series.p], container);
}

// Build both charts into `container` for one area's time series (from timeseries/<area>.json).
export function drawCharts(container, series, cutoffs) {
  container.innerHTML = "";
  const width = Math.max(260, container.clientWidth || 340);
  const x = toUnixSeconds(series.dates);

  // Chart 1: probability, recomputed each day; dots mark what the site actually published.
  const probTitle = document.createElement("p");
  probTitle.className = "chart-title";
  probTitle.textContent = "Forecast probability";
  container.appendChild(probTitle);
  const probOpts = baseOptions(width);
  probOpts.scales.y = { range: [0, 1] };
  probOpts.axes[1].values = (u, ticks) => ticks.map((t) => `${Math.round(t * 100)}%`);
  probOpts.series = [
    {},
    { label: "Probability", stroke: "#0e6e8c", width: 2, value: (u, v) => (v == null ? "–" : `${Math.round(v * 100)}%`) },
    { label: "As published", stroke: "#eb6834", width: 0, points: { show: true, size: 8, fill: "#eb6834" },
      value: (u, v) => (v == null ? "–" : `${Math.round(v * 100)}%`) },
  ];
  probOpts.hooks = { draw: [referenceLines([
    { value: cutoffs?.moderate, colour: TIER_COLOURS.Moderate },
    { value: cutoffs?.high, colour: TIER_COLOURS.High },
  ])] };
  new uPlot(probOpts, [x, series.p, series.issued_p], container);
  const note = document.createElement("p");
  note.className = "note";
  note.textContent = "Dashed lines: Moderate (amber) and High (red) cut-offs. Dots: forecasts as published (from the first day the site ran).";
  container.appendChild(note);

  // Chart 2: daily chlorophyll vs normal, only on days with a clear view (gaps = cloud).
  const chlTitle = document.createElement("p");
  chlTitle.className = "chart-title";
  chlTitle.textContent = "Chlorophyll vs normal (clear days only)";
  container.appendChild(chlTitle);
  const ratio = series.chl_log10_anomaly.map((v) => (v == null ? null : Math.pow(10, v)));
  const chlOpts = baseOptions(width);
  chlOpts.scales.y = { distr: 3, range: [0.25, 8] }; // log scale, quarter to 8× normal
  // Fixed, readable tick positions on the log scale: quarter, half, normal, double, ...
  chlOpts.axes[1].splits = () => [0.25, 0.5, 1, 2, 4, 8];
  chlOpts.axes[1].filter = (u, splits) => splits; // label them all (default: powers of 10 only)
  chlOpts.axes[1].values = (u, ticks) => ticks.map((t) => (t == null ? "" : t < 1 ? `${t === 0.25 ? "¼" : "½"}×` : `${t}×`));
  chlOpts.series = [
    {},
    { label: "× normal", stroke: "#0e6e8c", width: 0, points: { show: true, size: 6, fill: "#0e6e8c" },
      value: (u, v) => (v == null ? "cloud" : `${v.toFixed(1)}×`) },
  ];
  chlOpts.hooks = { draw: [referenceLines([{ value: 1, colour: "#8a8984" }])] }; // 1× = normal
  new uPlot(chlOpts, [x, ratio], container);
  const note2 = document.createElement("p");
  note2.className = "note";
  note2.textContent = "1× is this area's 2016–2022 median for the month. Chlorophyll is a proxy: some toxic algae cause problems without raising it.";
  container.appendChild(note2);
}
