// Place search: type a town (e.g. "Devonport") to see the harvest areas near it.
// The place list (web/data/places_tas.json, ~1,300 Tasmanian towns, suburbs and localities)
// comes from OpenStreetMap (© OpenStreetMap contributors, ODbL; design note D017) and is
// loaded only the first time someone searches. No outside service is called while searching.

import { TIER_LETTERS, formatPercent } from "./format.js";
import { escapeHtml } from "./list.js";

const PLACES_URL = "data/places_tas.json";
export const NEAR_KM = 25; // areas within this distance count as "near" a place (D017)
const FALLBACK_COUNT = 3; // if none are that close, show this many nearest areas instead
const MAX_SUGGESTIONS = 5; // other places with a similar name, offered as alternatives
const KIND_RANK = { city: 0, town: 1, suburb: 2, village: 3, hamlet: 4, locality: 5 };

let placesPromise = null;

// Load the place list once (later calls reuse the same download).
function loadPlaces() {
  if (!placesPromise) {
    placesPromise = fetch(PLACES_URL)
      .then((r) => (r.ok ? r.json() : { places: [] }))
      .then((d) => d.places)
      .catch(() => []);
  }
  return placesPromise;
}

// Distance in kilometres between two points (great-circle, "haversine" formula).
export function distanceKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2
    + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

// Places whose name matches the query: exact names first, then names starting with it, then
// names containing it; bigger places (city, town) before smaller ones within each group.
export function matchPlaces(places, query) {
  const q = query.trim().toLowerCase();
  if (q.length < 3) return [];
  const score = (p) => {
    const n = p.name.toLowerCase();
    const how = n === q ? 0 : n.startsWith(q) ? 1 : n.includes(q) ? 2 : 9;
    return how * 10 + (KIND_RANK[p.kind] ?? 9);
  };
  return places.map((p) => [score(p), p]).filter(([s]) => s < 90)
    .sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name))
    .map(([, p]) => p);
}

// Harvest areas near a place: all within NEAR_KM, nearest first; if there are none, the few
// nearest areas anyway (flagged so the text can say they are further away).
export function nearbyAreas(place, features) {
  const all = features
    .map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      return { feature: f, km: distanceKm(place.lat, place.lon, lat, lon) };
    })
    .sort((a, b) => a.km - b.km);
  const near = all.filter((a) => a.km <= NEAR_KM);
  return near.length ? { items: near, fallback: false } : { items: all.slice(0, FALLBACK_COUNT), fallback: true };
}

// Draw the "near <place>" block: the chosen place, other similarly named places to switch to,
// and one button per nearby harvest area (clicking it selects that area).
function renderBlock(el, matches, chosen, features, onSelect, onChoose) {
  const { items, fallback } = nearbyAreas(chosen, features);
  const others = matches.filter((p) => p !== chosen).slice(0, MAX_SUGGESTIONS - 1);
  el.innerHTML = `
    <p class="place-head">${fallback ? `No harvest areas within ${NEAR_KM} km of` : `Harvest areas within ${NEAR_KM} km of`}
      <strong>${escapeHtml(chosen.name)}</strong> <span class="place-kind">(${escapeHtml(chosen.kind)})</span>${fallback ? ". Nearest:" : ""}</p>
    <ul class="area-items place-areas"></ul>
    ${others.length ? `<p class="place-others">Other matches: ${others.map((p, i) =>
      `<button type="button" class="link-btn" data-i="${i}">${escapeHtml(p.name)} (${escapeHtml(p.kind)})</button>`).join(" · ")}</p>` : ""}`;
  const ul = el.querySelector(".place-areas");
  for (const { feature, km } of items) {
    const p = feature.properties;
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("aria-label", `${p.growing_area}, ${p.harvest_area}: ${p.tier}, ${formatPercent(p.probability)}, ${Math.round(km)} kilometres`);
    btn.innerHTML = `
      <span class="tier-dot tier-${p.tier}" aria-hidden="true">${TIER_LETTERS[p.tier]}</span>
      <span class="name">${escapeHtml(p.harvest_area)}<span class="growing">${escapeHtml(p.growing_area)}</span></span>
      <span class="pct" aria-hidden="true">${Math.round(km)} km · ${p.tier}</span>`;
    btn.addEventListener("click", () => onSelect(p.area_id, "list"));
    li.appendChild(btn);
    ul.appendChild(li);
  }
  el.querySelectorAll(".link-btn").forEach((b) => b.addEventListener("click", () => onChoose(others[Number(b.dataset.i)])));
  el.hidden = false;
}

// Connect place search to the search box. `onPlace(place)` lets the map fly to the place.
export function enablePlaceSearch({ searchEl, resultsEl, features, onSelect, onPlace }) {
  let lastQuery = "";
  let timer = null;
  // Wait until typing pauses (300 ms) so the map doesn't jump on every keystroke.
  searchEl.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(search, 300);
  });

  // Look up the current text and draw the result (or hide the block).
  async function search() {
    const q = searchEl.value;
    lastQuery = q;
    if (q.trim().length < 3) { resultsEl.hidden = true; resultsEl.innerHTML = ""; return; }
    const places = await loadPlaces();
    if (q !== lastQuery) return; // the user kept typing; a newer search will draw
    const matches = matchPlaces(places, q);
    if (!matches.length) { resultsEl.hidden = true; resultsEl.innerHTML = ""; return; }
    const choose = (place) => {
      renderBlock(resultsEl, matches, place, features, onSelect, choose);
      onPlace(place);
    };
    choose(matches[0]);
  }
}
