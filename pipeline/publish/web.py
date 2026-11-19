"""Copy the web app into the site folder and render the text pages (Phase 5).

  web/**                 -> site/  (index.html, css, js, vendored libraries)
  docs/about.md          -> site/about.html
  docs/model_card.md     -> site/model-card.html  (+ the images it links to)
(site/verification.html is written by the daily job: pipeline.publish.verification)

Run by the daily job (after the forecast files are written) and by the publish_web workflow
(when only the web files or these docs change). Locally, to preview:
    uv run python -m pipeline.publish.web --site _site
    uv run python -m http.server -d _site 8000
"""

import argparse
import html
import re
import shutil
from pathlib import Path

import markdown

from pipeline.config import REPO_ROOT

WEB_DIR = REPO_ROOT / "web"
DOCS_DIR = REPO_ROOT / "docs"
PAGES = {"about.html": ("About", "about.md"), "model-card.html": ("Model card", "model_card.md")}

TEMPLATE = """<!DOCTYPE html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}: Algal Bloom Outlook (experimental)</title>
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <header class="site-header">
    <div class="brand">
      <h1>Algal Bloom Outlook</h1>
      <p class="tagline">Satellite chlorophyll-a · Tasmania &amp; South Australia · Experimental</p>
    </div>
    <nav aria-label="Site">
      <a href="./">Map</a>
      <a href="about.html"{about_current}>About</a>
      <a href="verification.html"{verif_current}>Verification</a>
      <a href="model-card.html"{card_current}>Model card</a>
    </nav>
  </header>
  <main id="content" class="doc">
{body}
  </main>
  <footer class="site-footer">
    <p class="disclaimer"><strong>Experimental research tool.</strong> Indicates chlorophyll-a
    (algal biomass), not toxins or harmful species. Not a substitute for official harvest
    decisions by ShellMAP (Tasmania) or SASQAP (South Australia).</p>
    <p>Generated using E.U. Copernicus Marine Service Information. Sources and licences:
    <a href="about.html">About</a>.</p>
  </footer>
</body>
</html>
"""


def render_markdown(text: str) -> str:
    """Markdown -> HTML (tables, fenced code); repo paths to images become site paths."""
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    return body.replace('src="docs/img/', 'src="img/')


def linked_images(text: str) -> list[str]:
    """docs/img/... files mentioned in a markdown text (as images or `code` paths)."""
    return sorted(set(re.findall(r"docs/img/[\w.\-]+\.png", text)))


def page(title: str, md_name: str, current: str) -> tuple[str, list[str]]:
    """One rendered text page and the images it needs."""
    text = (DOCS_DIR / md_name).read_text(encoding="utf-8")
    # Figures the text refers to by path are shown at the end of the page.
    images = linked_images(text)
    if images:
        text += "\n\n## Figures\n\n" + "\n\n".join(
            f"`{img}`\n\n![{Path(img).stem.replace('_', ' ')}]({img})" for img in images
        )
    return render_page(title, render_markdown(text), current), images


def render_page(title: str, body_html: str, current: str) -> str:
    """Wrap HTML in the site's page template, marking `current` (a file name) in the nav."""
    mark = ' aria-current="page"'
    return TEMPLATE.format(
        title=html.escape(title),
        body=body_html,
        about_current=mark if current == "about.html" else "",
        verif_current=mark if current == "verification.html" else "",
        card_current=mark if current == "model-card.html" else "",
    )


def build(site: Path) -> None:
    """Copy web/ into `site` and write the text pages (forecast data files are untouched)."""
    site.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WEB_DIR, site, dirs_exist_ok=True)
    # The daily job writes verification.html; until its first run, show a short placeholder.
    if not (site / "verification.html").exists():
        body = render_markdown("# Verification\n\nFirst update pending. Updated daily.")
        (site / "verification.html").write_text(
            render_page("Verification", body, "verification.html"), encoding="utf-8"
        )
    for name, (title, md_name) in PAGES.items():
        content, images = page(title, md_name, name)
        (site / name).write_text(content, encoding="utf-8")
        for img in images:
            src = REPO_ROOT / img
            if src.exists():
                (site / "img").mkdir(exist_ok=True)
                shutil.copy2(src, site / "img" / src.name)


def main() -> None:
    """CLI: build the web part of the site into --site."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    build(parser.parse_args().site)
    print("web files and pages written")


if __name__ == "__main__":
    main()
