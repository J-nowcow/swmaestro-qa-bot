"""Unit tests for portfolio.parser."""
from pathlib import Path

import pytest

from portfolio.parser import (
    InvalidZipError,
    NoMarkdownError,
    ZipTooLargeError,
    parse_notion_zip,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample-notion-export.zip"


def _read_fixture() -> bytes:
    return FIXTURE.read_bytes()


def test_parse_returns_combined_markdown():
    result = parse_notion_zip(_read_fixture())
    assert "# About" in result.markdown
    assert "# Projects" in result.markdown
    assert "I am a backend developer" in result.markdown


def test_parse_strips_notion_id_suffix_from_filenames():
    result = parse_notion_zip(_read_fixture())
    # Notion id (32 hex chars) should not appear in markdown headings or body
    assert "abc123def4567890" not in result.markdown


def test_parse_extracts_images():
    result = parse_notion_zip(_read_fixture())
    assert len(result.images) == 2
    assert all(img.mime_type == "image/png" for img in result.images)
    assert all(img.base64 for img in result.images)


def test_parse_image_cap_30():
    """If a zip has more than 30 images, only first 30 are kept."""
    import io
    import zipfile

    from PIL import Image

    def _png():
        img = Image.new("RGB", (16, 16), "green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Page abcdef1234567890abcdef1234567890.md", "# Page\n")
        for i in range(40):
            z.writestr(f"img{i:03d}.png", _png())

    result = parse_notion_zip(buf.getvalue())
    assert len(result.images) == 30
    assert result.stats.image_truncated is True
    assert result.stats.image_count == 40


def test_parse_stats_populated():
    result = parse_notion_zip(_read_fixture())
    assert result.stats.page_count == 2
    assert result.stats.image_count == 2
    assert result.stats.image_truncated is False
    assert result.stats.total_chars > 0


def test_parse_invalid_zip_raises():
    with pytest.raises(InvalidZipError):
        parse_notion_zip(b"not a zip file at all")


def test_parse_zip_with_no_markdown_raises():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "no md here")
    with pytest.raises(NoMarkdownError):
        parse_notion_zip(buf.getvalue())


def test_parse_zip_too_large_raises():
    import io
    import zipfile

    from portfolio.parser import UNCOMPRESSED_LIMIT, ZipTooLargeError

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("page.md", "# x\n")
        # Highly compressible — actual zip stays small but uncompressed exceeds limit
        z.writestr("big.bin", b"A" * (UNCOMPRESSED_LIMIT + 1))
    with pytest.raises(ZipTooLargeError):
        parse_notion_zip(buf.getvalue())


def test_parse_handles_nested_zip():
    """Notion sometimes exports as zip-in-zip. Parser should auto-unwrap."""
    import io
    import zipfile

    # Build inner zip with actual md content
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w", zipfile.ZIP_DEFLATED) as inner_z:
        inner_z.writestr(
            "About abcdef1234567890abcdef1234567890.md",
            "# About\n\nNested content.\n",
        )
    inner_bytes = inner_buf.getvalue()

    # Wrap it in outer zip (Notion style: ExportBlock-xxx.zip)
    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w", zipfile.ZIP_DEFLATED) as outer_z:
        outer_z.writestr("ExportBlock-abc123-Part-1.zip", inner_bytes)

    result = parse_notion_zip(outer_buf.getvalue())
    assert "# About" in result.markdown
    assert "Nested content" in result.markdown
    assert result.stats.page_count == 1


def test_parse_does_not_strip_long_hex_sequences():
    """40-char git SHAs should not be stripped (they're > 32 chars)."""
    import io
    import zipfile

    long_sha = "abcdef1234567890" * 3  # 48 chars hex
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "Page abcdef1234567890abcdef1234567890.md",
            f"# Page\n\nFixed in commit {long_sha}\n",
        )
    result = parse_notion_zip(buf.getvalue())
    assert long_sha in result.markdown  # long sequence preserved
    assert "abcdef1234567890abcdef1234567890.md" not in result.markdown  # 32-char id stripped
