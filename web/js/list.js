// The list of harvest areas in the sidebar: sorted by risk, searchable, keyboard friendly.
// It's also the "table view" of the map, so nothing depends on seeing the colours.

import { TIER_LETTERS, formatPercent } from "./format.js";

// Order used for sorting: High first, then Moderate, then Low.
const TIER_RANK = { High: 0, Moderate: 1, Low: 2 };

// Build the list once, wire up the search box, and return a function that marks the
// currently selected area.
export function createList({ features, listEl, searchEl, countEl, onSelect }) {
  // Sort by tier, then by probability (highest first), then by name.
  const sorted = [...features].sort((a, b) => {
    const pa = a.properties, pb = b.properties;
    return (TIER_RANK[pa.tier] - TIER_RANK[pb.tier])
      || ((pb.probability ?? 0) - (pa.probability ?? 0))
      || pa.growing_area.localeCompare(pb.growing_area);
  });

  // One <li><button> per area. Buttons are reachable with Tab and activated with Enter/Space.
  const items = sorted.map((f) => {
    const p = f.properties;
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.areaId = p.area_id;
    btn.setAttribute("aria-label", `${p.growing_area}, ${p.harvest_area}: ${p.tier} risk, ${formatPercent(p.probability)}`);
    btn.innerHTML = `
      <span class="tier-dot tier-${p.tier}" aria-hidden="true">${TIER_LETTERS[p.tier]}</span>
      <span class="name">${escapeHtml(p.harvest_area)}<span class="growing">${escapeHtml(p.growing_area)}</span></span>
      <span class="pct" aria-hidden="true">${p.tier} · ${formatPercent(p.probability)}</span>`;
    btn.addEventListener("click", () => onSelect(p.area_id, "list"));
    li.appendChild(btn);
    listEl.appendChild(li);
    return { li, text: `${p.growing_area} ${p.harvest_area}`.toLowerCase() };
  });

  // Show how many areas match the search, and how many are in each tier.
  function updateCount(shown) {
    const counts = { High: 0, Moderate: 0, Low: 0 };
    features.forEach((f) => { counts[f.properties.tier] += 1; });
    const head = shown === features.length ? `${features.length} areas` : `${shown} of ${features.length} areas`;
    countEl.textContent = `${head} · High ${counts.High} · Moderate ${counts.Moderate} · Low ${counts.Low}`;
  }

  // Filter the list as the user types (matches growing-area or harvest-area names).
  searchEl.addEventListener("input", () => {
    const q = searchEl.value.trim().toLowerCase();
    let shown = 0;
    items.forEach(({ li, text }) => {
      const match = !q || text.includes(q);
      li.hidden = !match;
      if (match) shown += 1;
    });
    updateCount(shown);
  });
  updateCount(items.length);

  // Mark the selected area in the list (for screen readers and the highlight colour).
  return function markSelected(areaId) {
    listEl.querySelectorAll("button").forEach((b) => {
      b.setAttribute("aria-current", b.dataset.areaId === areaId ? "true" : "false");
    });
  };
}

// Make text safe to put inside HTML (area names come from a data file).
export function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
