"""Turn the README tour frames into a small animated GIF (Phase 6).

Run after `node tools/screenshots.mjs`:
    uv run python tools/make_gif.py
Reads docs/img/readme/frames/*.png and writes docs/img/readme/tour.gif (scaled to 960 px wide,
a shared 128-colour palette, 1.8 s per frame), then deletes the frames (they are not committed).
"""

import shutil
from pathlib import Path

from PIL import Image

FRAMES = Path("docs/img/readme/frames")
OUT = Path("docs/img/readme/tour.gif")
WIDTH, COLOURS, FRAME_MS = 960, 128, 1800


def main() -> None:
    """Build the GIF and remove the frames."""
    paths = sorted(FRAMES.glob("*.png"))
    if not paths:
        raise SystemExit("no frames; run: node tools/screenshots.mjs")
    images = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        images.append(im)
    # One palette for all frames keeps colours stable and the file small.
    palette = images[0].quantize(colors=COLOURS, method=Image.Quantize.MEDIANCUT)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0,
                   optimize=True)  # fmt: skip
    shutil.rmtree(FRAMES)
    print(f"{OUT}: {len(frames)} frames, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
