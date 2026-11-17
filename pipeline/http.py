"""A tiny, polite HTTP helper used by every fetch script.

Why a shared helper: every request must carry our descriptive User-Agent and a timeout,
and must fail loudly on HTTP errors rather than silently saving an error page.
"""

import urllib.robotparser
from urllib.parse import urlparse

import requests

from pipeline.config import REQUEST_TIMEOUT_S, USER_AGENT

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})


def get(url: str, params: dict | None = None, stream: bool = False) -> requests.Response:
    """GET a URL with our User-Agent and timeout. Raises on any non-2xx response."""
    resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT_S, stream=stream)
    resp.raise_for_status()
    return resp


def robots_allows(url: str) -> bool | None:
    """Check robots.txt for `url` using our User-Agent.

    Returns True/False if robots.txt was read, or None if it could not be fetched
    (in which case the caller should stop and check the site's terms by hand).
    """
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = _session.get(robots_url, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException:
        return None
    if resp.status_code == 404:
        return True  # no robots.txt means no restrictions are declared
    if not resp.ok:
        return None
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(resp.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)
