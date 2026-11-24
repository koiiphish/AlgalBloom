"""Phase 5 web build: pages render, files are copied, JS parses, lakes are masked."""

import json
import shutil
import subprocess

import numpy as np
import pytest

from pipeline.publish import rasters, web


def test_build_writes_pages_and_assets(tmp_path):
    """The site gets the app, both text pages (with the right nav item marked) and figures."""
    web.build(tmp_path)
    for name in ("index.html", "about.html", "model-card.html", "css/style.css", "js/main.js",
                 "vendor/maplibre-gl-6.19.0/maplibre-gl.mjs",
                 "vendor/maplibre-gl-6.19.0/LICENSE.txt", "vendor/uplot-1.6.32/LICENSE"):  # fmt: skip
        assert (tmp_path / name).exists(), name
    about = (tmp_path / "about.html").read_text(encoding="utf-8")
    assert 'href="about.html" aria-current="page"' in about
    assert "not</strong> a substitute" in about or "not a substitute" in about.lower()
    card = (tmp_path / "model-card.html").read_text(encoding="utf-8")
    assert "<table>" in card and 'src="img/' in card
    assert any((tmp_path / "img").glob("*.png"))


def test_every_page_carries_the_disclaimer(tmp_path):
    """The safety disclaimer must be on the map page and both text pages."""
    web.build(tmp_path)
    for name in ("index.html", "about.html", "model-card.html"):
        text = (tmp_path / name).read_text(encoding="utf-8").lower()
        assert "not a substitute for official" in text or "not</strong> a substitute" in text, name


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_javascript_modules_parse(tmp_path):
    """Every web/js module is valid JavaScript (checked as an ES module with node --check)."""
    for js in sorted(web.WEB_DIR.glob("js/*.js")):
        copy = tmp_path / (js.stem + ".mjs")
        copy.write_text(js.read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True)
        assert result.returncode == 0, f"{js.name}: {result.stderr}"


def test_sea_connected_drops_lakes_keeps_estuaries():
    """Water enclosed by land (a lake) is dropped; water reaching the box edge is kept."""
    land = np.zeros((7, 7), dtype=bool)
    land[1:6, 1:6] = True  # an island...
    land[3, 3] = False  # ...with a one-pixel lake
    land[3, 5] = False  # and an inlet reaching the sea at the right edge via (3, 6)
    sea = rasters.sea_connected(land)
    assert not sea[3, 3] and sea[3, 5] and sea[0, 0]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_place_search_logic():
    """Town search: exact names rank first; Devonport finds Port Sorell (~19 km); a town with
    no area within 25 km falls back to the nearest three."""
    js = web.WEB_DIR / "js" / "places.js"
    script = f"""
import {{ matchPlaces, nearbyAreas }} from "{js.as_uri()}";
const places = [
  {{ name: "Devonport", kind: "city", lat: -41.1798, lon: 146.3613 }},
  {{ name: "East Devonport", kind: "suburb", lat: -41.18, lon: 146.38 }},
  {{ name: "Queenstown", kind: "town", lat: -42.08, lon: 145.555 }},
];
const f = (id, lon, lat) => ({{ geometry: {{ coordinates: [lon, lat] }}, properties: {{ area_id: id }} }});
const features = [f("port_sorell", 146.556, -41.164), f("far1", 148.0, -42.5), f("far2", 147.9, -43.0)];
const m = matchPlaces(places, "devonport");
const near = nearbyAreas(m[0], features);
const q = nearbyAreas(places[2], features);
console.log(JSON.stringify({{ first: m[0].name, n: m.length, near: near.items.map((x) => x.feature.properties.area_id),
  km: Math.round(near.items[0].km), fallback: q.fallback, qn: q.items.length, short: matchPlaces(places, "de").length }}));
"""
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["first"] == "Devonport" and r["n"] == 2 and r["near"] == ["port_sorell"]
    assert 15 <= r["km"] <= 20 and r["fallback"] and r["qn"] == 3 and r["short"] == 0
