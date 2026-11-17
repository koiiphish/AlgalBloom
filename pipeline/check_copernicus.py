"""Check that the Copernicus Marine credentials in `.env` work, without printing them.

Run:  uv run python -m pipeline.check_copernicus
"""

import os

import copernicusmarine
from dotenv import load_dotenv

from pipeline.config import REPO_ROOT

REQUIRED = ("COPERNICUSMARINE_SERVICE_USERNAME", "COPERNICUSMARINE_SERVICE_PASSWORD")


def main() -> None:
    """Load .env, confirm both variables are set, then ask Copernicus if they are valid."""
    load_dotenv(REPO_ROOT / ".env")
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)}")
    # check_credentials_valid=True only verifies; it does not write a config file.
    ok = copernicusmarine.login(check_credentials_valid=True)
    print("Copernicus credentials are VALID" if ok else "Copernicus credentials are INVALID")


if __name__ == "__main__":
    main()
