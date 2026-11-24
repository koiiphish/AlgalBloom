"""One-off: Tasmanian place names (towns, suburbs, localities) for the map's place search (D017).

Source: OpenStreetMap via the Overpass API (https://overpass-api.de/api/interpreter), ONE request.
Overpass robots.txt disallows /api/ for crawlers, but its documentation explicitly invites
programmatic use ("a maximum of about 10000 requests per day ... below about 1 GB per day",
https://dev.overpass-api.de/overpass-doc/en/preface/commons.html, read 2026-11-24); same
reasoning as Open-Meteo in D003.

Licence: OpenStreetMap data is © OpenStreetMap contributors, Open Database License (ODbL 1.0).
The derived list web/data/places_tas.json is therefore also under the ODbL, and the site credits
OpenStreetMap. Only name, kind and a rounded position are kept.

Run:  uv run python -m pipeline.fetch.osm_places
Output: data/raw/osm/places_tas_raw.json (git-ignored), web/data/places_tas.json (published)
"""

import json

import requests

from pipeline.config import RAW_DIR, REPO_ROOT, REQUEST_TIMEOUT_S, USER_AGENT

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TAS_BBOX = (-43.8, 143.5, -39.4, 148.6)  # south, west, north, east (incl. King & Flinders Is.)
KINDS = ("city", "town", "village", "hamlet", "suburb", "locality")
RAW_PATH = RAW_DIR / "osm" / "places_tas_raw.json"
OUT_PATH = REPO_ROOT / "web" / "data" / "places_tas.json"


def query() -> str:
    """Overpass QL: named places of the listed kinds inside the Tasmania box, with centres."""
    s, w, n, e = TAS_BBOX
    kinds = "|".join(KINDS)
    sel = f'["place"~"^({kinds})$"]["name"]({s},{w},{n},{e})'
    return f"[out:json][timeout:90];(node{sel};way{sel};relation{sel};);out center tags;"


def fetch() -> dict:
    """Send the single request (or reuse the cached raw response)."""
    if RAW_PATH.exists():
        return json.loads(RAW_PATH.read_text(encoding="utf-8"))
    resp = requests.post(OVERPASS_URL, data={"data": query()}, timeout=max(REQUEST_TIMEOUT_S, 120),
                         headers={"User-Agent": USER_AGENT})  # fmt: skip
    resp.raise_for_status()
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(resp.text, encoding="utf-8")
    return resp.json()


def places(raw: dict) -> list[dict]:
    """Compact list: name, kind, lat, lon (4 decimals, ~10 m), de-duplicated by name + kind."""
    out, seen = [], set()
    rank = {k: i for i, k in enumerate(KINDS)}
    for el in raw.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        name, kind = tags.get("name"), tags.get("place")
        if not name or lat is None or kind not in rank or (name, kind) in seen:
            continue
        seen.add((name, kind))
        out.append({"name": name, "kind": kind, "lat": round(lat, 4), "lon": round(lon, 4)})
    return sorted(out, key=lambda p: (rank[p["kind"]], p["name"]))


def main() -> None:
    """Fetch once and write the published list."""
    plist = places(fetch())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "source": "OpenStreetMap via Overpass API, retrieved 2026-11-24",
        "licence": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
        "places": plist,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")  # fmt: skip
    kinds = {k: sum(p["kind"] == k for p in plist) for k in KINDS}
    print(f"{len(plist)} places {kinds}; {OUT_PATH.stat().st_size / 1024:.0f} KB -> {OUT_PATH}")


if __name__ == "__main__":
    main()
