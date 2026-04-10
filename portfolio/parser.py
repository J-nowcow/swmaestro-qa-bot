"""Parse Notion markdown-export zip into text and images."""
from __future__ import annotations

import base64
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from PIL import Image

# Notion appends a 32-character hex id to filenames and headings.
_NOTION_ID_RE = re.compile(r"\s[0-9a-f]{32}(?![0-9a-f])")

IMAGE_CAP = 30
IMAGE_MAX_DIM = 1024
IMAGE_MAX_BYTES = 4 * 1024 * 1024
UNCOMPRESSED_LIMIT = 50 * 1024 * 1024  # 50 MB zip-bomb guard
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUPPORTED_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class InvalidZipError(Exception):
    """Raised when the uploaded bytes are not a valid zip archive."""


class NoMarkdownError(Exception):
    """Raised when the zip has no .md files."""


class ZipTooLargeError(Exception):
    """Raised when uncompressed size exceeds the safety limit."""


@dataclass
class ImageData:
    filename: str
    mime_type: str
    base64: str
    original_index: int


@dataclass
class PortfolioStats:
    page_count: int
    image_count: int  # total images present in the zip
    image_truncated: bool
    total_chars: int


@dataclass
class ParsedPortfolio:
    markdown: str
    images: list[ImageData] = field(default_factory=list)
    stats: PortfolioStats = field(
        default_factory=lambda: PortfolioStats(0, 0, False, 0)
    )


def _strip_notion_ids(text: str) -> str:
    return _NOTION_ID_RE.sub("", text)


def _resize_to_base64(raw: bytes, mime_type: str) -> str | None:
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception:
        return None
    img.thumbnail((IMAGE_MAX_DIM, IMAGE_MAX_DIM))
    out = io.BytesIO()
    fmt = "PNG" if mime_type == "image/png" else "JPEG"
    if fmt == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(out, format=fmt)
    return base64.b64encode(out.getvalue()).decode("ascii")


def _unwrap_nested_zip(zip_bytes: bytes) -> bytes:
    """If the zip contains a single .zip file inside, extract and return its bytes.

    Notion sometimes exports as a double-zipped file:
    outer.zip → ExportBlock-xxx.zip → actual .md + images.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return zip_bytes

    entries = [i for i in zf.infolist() if not i.is_dir()]
    if (
        len(entries) == 1
        and PurePosixPath(entries[0].filename).suffix.lower() == ".zip"
    ):
        with zf.open(entries[0]) as inner:
            return inner.read()

    zf.close()
    return zip_bytes


def parse_notion_zip(zip_bytes: bytes) -> ParsedPortfolio:
    """Parse a Notion markdown-export zip.

    - Handles double-zipped Notion exports (zip-in-zip).
    - Combines all .md files in alphabetical order.
    - Strips Notion's 32-char hex id suffixes.
    - Extracts up to IMAGE_CAP images, resized to IMAGE_MAX_DIM, base64 encoded.

    Raises:
        InvalidZipError: bytes are not a valid zip.
        NoMarkdownError: zip has zero .md files.
        ZipTooLargeError: uncompressed size > UNCOMPRESSED_LIMIT.
    """
    zip_bytes = _unwrap_nested_zip(zip_bytes)

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise InvalidZipError(str(e)) from e

    with zf:
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        if total_uncompressed > UNCOMPRESSED_LIMIT:
            raise ZipTooLargeError(
                f"uncompressed size {total_uncompressed} > {UNCOMPRESSED_LIMIT}"
            )

        md_names: list[str] = []
        image_names: list[str] = []
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            ext = PurePosixPath(name).suffix.lower()
            if ext == ".md":
                md_names.append(name)
            elif ext in SUPPORTED_IMAGE_EXTS:
                image_names.append(name)

        if not md_names:
            raise NoMarkdownError("zip contains no .md files")

        md_names.sort()
        image_names.sort()

        md_chunks: list[str] = []
        for name in md_names:
            with zf.open(name) as f:
                text = f.read().decode("utf-8", errors="replace")
            md_chunks.append(_strip_notion_ids(text))
        combined_md = "\n\n".join(md_chunks)

        images: list[ImageData] = []
        for idx, name in enumerate(image_names[:IMAGE_CAP]):
            info = zf.getinfo(name)
            if info.file_size > IMAGE_MAX_BYTES:
                continue
            with zf.open(name) as f:
                raw = f.read()
            ext = PurePosixPath(name).suffix.lower()
            mime = SUPPORTED_MIME.get(ext, "application/octet-stream")
            b64 = _resize_to_base64(raw, mime)
            if b64 is None:
                continue
            images.append(
                ImageData(
                    filename=PurePosixPath(name).name,
                    mime_type=mime,
                    base64=b64,
                    original_index=idx,
                )
            )

        return ParsedPortfolio(
            markdown=combined_md,
            images=images,
            stats=PortfolioStats(
                page_count=len(md_names),
                image_count=len(image_names),
                image_truncated=len(image_names) > IMAGE_CAP,
                total_chars=len(combined_md),
            ),
        )
