"""Official boundary maps: ShellMAP management-plan PDFs per growing area (Phase 6, D018).

The ShellMAP "Growing and harvest areas" page links one management plan per growing area
(e.g. /Documents/Management%20Plan%20-%20Great%20Bay.pdf); these contain the official area
maps. The site links each harvest area's panel to its growing area's plan, so users can check
exact boundaries without us publishing the (unlicensed) polygons.

Checked 2026-11-24: 26 plan links on the page, every one HTTP 200 application/pdf; 26 of our
29 growing areas match by name (letters only, case-insensitive). Missionary Bay, Simpsons Bay
and Triabunna have no plan on the page and fall back to the ShellMAP page.

Run:  uv run python -m pipeline.labels.management_plans     (one page request)
Output: labels/reference/tas_management_plans.json (committed)
"""

import json
import re
from datetime import date
from urllib.parse import unquote

from pipeline.config import REPO_ROOT
from pipeline.http import get

PAGE_URL = "https://nre.tas.gov.au/aquaculture/shellmap/growing-and-harvest-areas"
BASE_URL = "https://nre.tas.gov.au"
OUT_PATH = REPO_ROOT / "labels" / "reference" / "tas_management_plans.json"
LINK = re.compile(r'href="(/Documents/Management%20Plan%20-%20[^"]+\.pdf)"')


def norm(name: str) -> str:
    """Comparable growing-area name: letters only, lower case ('Pipe Clay Lagoon' ->
    'pipeclaylagoon', matching 'Pipeclay Lagoon')."""
    return re.sub(r"[^a-z]", "", name.lower())


def plans_from_html(html: str) -> dict[str, dict[str, str]]:
    """{normalised growing area: {"name", "url"}} from the page's management-plan links."""
    out = {}
    for path in sorted(set(LINK.findall(html))):
        name = unquote(path).removeprefix("/Documents/Management Plan - ").removesuffix(".pdf")
        out[norm(name)] = {"name": name, "url": BASE_URL + path}
    return out


def main() -> None:
    """Fetch the page once and write the lookup."""
    plans = plans_from_html(get(PAGE_URL).text)
    OUT_PATH.write_text(json.dumps({
        "source": PAGE_URL,
        "retrieved": date.today().isoformat(),
        "note": "ShellMAP management plans (contain official area maps). © State of Tasmania.",
        "plans": plans,
    }, indent=1), encoding="utf-8")  # fmt: skip
    print(f"{len(plans)} plans -> {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
