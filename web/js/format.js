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

// Turn a full timestamp (e.g. "2026-11-19T07:34:45+00:00") into Hobart local time.
export function formatHobartTime(isoTimestamp) {
  if (!isoTimestamp) return "unknown";
  return new Date(isoTimestamp).toLocaleString("en-AU", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    timeZone: "Australia/Hobart", timeZoneName: "short",
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

// Days between two ISO dates (b - a), as a whole number.
export function daysBetween(a, b) {
  return Math.round((new Date(b) - new Date(a)) / 86400000);
}
