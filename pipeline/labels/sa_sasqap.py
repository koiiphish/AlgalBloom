"""South Australia (PIRSA SASQAP) harvest-area status: placeholder.

Disabled on purpose. pir.sa.gov.au returns HTTP 403 to automated requests (checked
2026-11-17), and our rules forbid working around that. Timothy has asked PIRSA for
permission and for the boundary data. When they reply, implement `fetch_status()` here
(same snapshot columns as Tasmania, region="sa") and set ENABLED = True.
"""

ENABLED = False


def status_message() -> str:
    """One-line log message explaining whether SA was archived."""
    if ENABLED:
        return "sa: enabled"  # pragma: no cover - not implemented yet
    return "sa: skipped (awaiting PIRSA permission; see docs/data_sources.md)"
