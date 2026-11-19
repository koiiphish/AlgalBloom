// Small helpers that turn numbers and dates into plain-English text.
// No dependencies. Every function is commented for readers new to JavaScript.

// The three risk tiers, in order. Shared by the map, list and panel.
export const TIERS = ["Low", "Moderate", "High"];

// Tier colours (must match css/style.css). Low is grey on purpose, not green, so it is never
// read as "safe to harvest".
export const TIER_COLOURS = { Low: "#8a8984", Moderate: "#fab219", High: "#d03b3b" };

// Letter shown inside each map marker, so colour is never the only cue.
export const TIER_LETTERS = { Low: "L", Moderate: "M", High: "H" };

// Turn "2026-11-19" into a readable date such as "Thu 19 Nov 2026".
// The date string has no time, so we build it in UTC to avoid shifting a day.
export function formatDate(isoDate, withYear = true) {
  if (!isoDate) return "unknown";
  const d = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString("en-AU", {
    weekday: "short", day: "numeric", month: "short",
    year: withYear ? "numeric" : undefined, timeZone: "UTC",
  });
}

// Turn a full timestamp (e.g. "2026-11-19T07:34:45+00:00") into short Hobart local time,
// e.g. "19 Nov, 6:34 pm AEDT".
export function formatHobartTime(isoTimestamp) {
  if (!isoTimestamp) return "unknown";
  return new Date(isoTimestamp).toLocaleString("en-AU", {
    day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
    timeZone: "Australia/Hobart", timeZoneName: "short",
  });
}

// A short date range, e.g. "20–26 Nov" (or "28 Nov – 4 Dec" across months).
export function formatRange(fromIso, toIso) {
  if (!fromIso || !toIso) return "unknown";
  const opts = { day: "numeric", month: "short", timeZone: "UTC" };
  const a = new Date(`${fromIso.slice(0, 10)}T00:00:00Z`);
  const b = new Date(`${toIso.slice(0, 10)}T00:00:00Z`);
  if (a.getUTCMonth() === b.getUTCMonth()) {
    return `${a.getUTCDate()}–${b.toLocaleDateString("en-AU", opts)}`;
  }
  return `${a.toLocaleDateString("en-AU", opts)} – ${b.toLocaleDateString("en-AU", opts)}`;
}

// A short date without weekday or year, e.g. "17 Nov".
export function formatShortDate(isoDate) {
  if (!isoDate) return "unknown";
  return new Date(`${isoDate.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-AU", {
    day: "numeric", month: "short", timeZone: "UTC",
  });
}

// Show a probability (0-1) as a whole percentage, e.g. 0.426 -> "43%".
export function formatPercent(p) {
  return p == null ? "n/a" : `${Math.round(p * 100)}%`;
}

// Convert a log10 chlorophyll anomaly into "times normal", e.g. 0.30 -> "2.0×".
export function ratioText(log10Anomaly) {
  if (log10Anomaly == null) return "no clear view";
  return `${Math.pow(10, log10Anomaly).toFixed(1)}×`;
}

// One plain-English sentence describing the evidence behind an area's forecast.
export function evidenceSentence(ev) {
  if (!ev || ev.score_log10_anomaly == null) {
    return "No clear satellite view in the last 14 days, so this uses the usual risk for the time of year.";
  }
  const trend = {
    rising: ", and rising",
    falling: ", and falling",
    steady: ", and about steady",
    unknown: "",
  }[ev.trend] ?? "";
  return `Satellite chlorophyll has been ${ratioText(ev.score_log10_anomaly)} this area's normal for the month${trend}.`;
}
