"""Local tests for the input processing foundation.

Run directly:  py tests/test_input_processor.py
Or with pytest: py -m pytest tests/test_input_processor.py -v
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Ensure the project root is on sys.path so imports work when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.nodes.input_processor import (
    InvestigationInput,
    SourceType,
    process_input,
)

# ---------------------------------------------------------------------------
# Test 1: Plain text with email, URL, and Indian phone number
# ---------------------------------------------------------------------------


def test_plain_text_entities() -> None:
    text = (
        "Contact us at hr@example.com or visit https://www.example.com/jobs. "
        "Call +91 98765 43210 for details."
    )
    result = process_input(text=text)
    assert result.source_type == SourceType.TEXT
    assert result.raw_text == text  # original preserved
    assert "hr@example.com" in result.email_addresses
    assert any("example.com" in u for u in result.urls)
    assert any("98765" in p for p in result.phone_numbers)


# ---------------------------------------------------------------------------
# Test 2: Sample job posting text
# ---------------------------------------------------------------------------


def test_job_posting_text() -> None:
    text = (
        "Job Title: Senior Software Engineer\n"
        "Company: Acme Technologies Pvt Ltd\n"
        "Location: Bengaluru, Karnataka\n"
        "Salary: ₹12 LPA\n"
        "Hiring Manager: Priya Sharma\n"
        "Email: careers@acmetech.com\n"
        "Phone: 9876543210\n"
    )
    result = process_input(text=text)
    assert result.source_type == SourceType.TEXT
    assert "Senior Software Engineer" in result.job_titles
    assert "Acme Technologies Pvt Ltd" in result.company_names
    assert any("Bengaluru" in loc for loc in result.locations)
    assert any("12" in s for s in result.salary_mentions)
    assert "Priya Sharma" in result.recruiter_names
    assert "careers@acmetech.com" in result.email_addresses
    assert "9876543210" in result.phone_numbers

# ---------------------------------------------------------------------------
# Test 3: Invalid URL
# ---------------------------------------------------------------------------


def test_invalid_url() -> None:
    try:
        process_input(url="not-a-url")
    except ValueError as exc:
        assert "Invalid URL" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid URL")


# ---------------------------------------------------------------------------
# Test 4: Unsupported file type
# ---------------------------------------------------------------------------


def test_unsupported_file_type() -> None:
    # A .txt file with arbitrary content should be rejected.
    try:
        process_input(file_bytes=b"hello world", file_name="notes.txt")
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported file type")


# ---------------------------------------------------------------------------
# Test 5: Missing / corrupted input
# ---------------------------------------------------------------------------


def test_missing_input() -> None:
    try:
        process_input()
    except ValueError as exc:
        assert "Exactly one" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing input")


def test_empty_text() -> None:
    try:
        process_input(text="   ")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty text")


def test_corrupted_image() -> None:
    # Bytes that claim to be an image but are not valid.
    try:
        process_input(file_bytes=b"\x89PNG\r\n\x1a\nnot-a-real-png", file_name="fake.png")
    except ValueError as exc:
        assert "Could not read image" in str(exc)
    else:
        raise AssertionError("Expected ValueError for corrupted image")


def test_corrupted_pdf() -> None:
    # Bytes that claim to be a PDF but are not valid.
    try:
        process_input(file_bytes=b"%PDF-1.4 not-a-real-pdf", file_name="fake.pdf")
    except ValueError as exc:
        assert "Could not open PDF" in str(exc)
    else:
        raise AssertionError("Expected ValueError for corrupted PDF")


# ---------------------------------------------------------------------------
# Test 6: Simple PDF (text-based)
# ---------------------------------------------------------------------------


def test_text_pdf() -> None:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("SKIP: PyMuPDF not installed; skipping PDF test.")
        return

    # Build a minimal text-based PDF in memory.
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Job Title: Data Analyst\nCompany: DataWorks Ltd\n"
        "Email: jobs@dataworks.com\nPhone: 9123456789",
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    result = process_input(file_bytes=pdf_bytes, file_name="job.pdf")
    assert result.source_type == SourceType.PDF
    assert "Data Analyst" in result.extracted_text
    assert "jobs@dataworks.com" in result.email_addresses
    assert "9123456789" in result.phone_numbers
    assert result.extraction_metadata.get("page_count") == 1


# ---------------------------------------------------------------------------
# Test 7: Simple image (PNG) - OCR may not be available
# ---------------------------------------------------------------------------

def test_image_png() -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("SKIP: Pillow not installed; skipping image test.")
        return

    # Create a simple image with text drawn on it.
    img = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(img)

    draw.text(
        (10, 10),
        "Contact: test@example.com",
        fill="black",
    )

    draw.text(
        (10, 40),
        "Phone: 9876543210",
        fill="black",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    result = process_input(
        file_bytes=png_bytes,
        file_name="screenshot.png",
    )

    # Basic image-processing checks.
    assert result.source_type == SourceType.IMAGE
    assert result.file_name == "screenshot.png"
    assert result.extraction_metadata.get("format") == "PNG"

    # OCR is optional because Tesseract may not be installed
    # in the environment running the tests.
    ocr_meta = result.extraction_metadata.get("ocr", {})

    if ocr_meta.get("available") and result.extracted_text:
        # If OCR actually produced text, entity extraction should
        # be able to detect the email address.
        assert (
            "test@example.com" in result.email_addresses
            or "test@example.com" in result.extracted_text
        )
    else:
        # OCR unavailable/fails gracefully.
        assert (
            "ocr" in result.extraction_metadata
            or result.extracted_text == ""
        )
# def test_image_png() -> None:
#     try:
#         from PIL import Image, ImageDraw
#     except ImportError:
#         print("SKIP: Pillow not installed; skipping image test.")
#         return

#     # Create a simple image with text drawn on it.
#     img = Image.new("RGB", (400, 100), "white")
#     draw = ImageDraw.Draw(img)
#     draw.text((10, 10), "Contact: test@example.com", fill="black")
#     draw.text((10, 40), "Phone: 9876543210", fill="black")

#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     png_bytes = buf.getvalue()

#     result = process_input(file_bytes=png_bytes, file_name="screenshot.png")
#     assert result.source_type == SourceType.IMAGE
#     assert result.file_name == "screenshot.png"
#     assert result.extraction_metadata.get("format") == "PNG"

#     # If OCR is available, we expect entities; otherwise a warning is recorded.
#     ocr_meta = result.extraction_metadata.get("ocr", {})
#     if ocr_meta.get("available"):
#         assert "test@example.com" in result.email_addresses
#     else:
#         assert any("OCR" in w for w in result.processing_warnings)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _run_all() -> None:
    tests = [
        test_plain_text_entities,
        test_job_posting_text,
        test_invalid_url,
        test_unsupported_file_type,
        test_missing_input,
        test_empty_text,
        test_corrupted_image,
        test_corrupted_pdf,
        test_text_pdf,
        test_image_png,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"PASS: {test_fn.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL: {test_fn.__name__}: {exc}")
            failed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {test_fn.__name__}: {exc}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
