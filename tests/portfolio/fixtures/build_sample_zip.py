"""Generate a tiny Notion-export-style zip for tests.

Run once to (re)create sample-notion-export.zip in this directory.
"""
import io
import zipfile
from pathlib import Path

from PIL import Image

OUT = Path(__file__).parent / "sample-notion-export.zip"


def _png_bytes(color, size=(64, 64)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build():
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        # Notion adds a 32-char hex id suffix to each filename
        z.writestr(
            "About abc123def4567890abcdef1234567890.md",
            "# About\n\nI am a backend developer.\n",
        )
        z.writestr(
            "Projects abc123def4567890abcdef1234567891.md",
            "# Projects\n\n## Project A\n\n![diagram](Projects abc123def4567890abcdef1234567891/architecture.png)\n",
        )
        z.writestr(
            "Projects abc123def4567890abcdef1234567891/architecture.png",
            _png_bytes("blue"),
        )
        z.writestr(
            "Projects abc123def4567890abcdef1234567891/screenshot.png",
            _png_bytes("red"),
        )

    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
