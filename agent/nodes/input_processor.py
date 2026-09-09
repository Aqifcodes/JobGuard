"""Input processing foundation for the job scam detector.

This module converts heterogeneous inputs (plain text, job posting URLs,
screenshots/images, and PDF documents) into a single standardized
``InvestigationInput`` representation that downstream investigation nodes
can consume.

This layer is strictly about *preparing reliable structured evidence*. It
does NOT classify anything as a scam, generate risk scores or verdicts, call
LLMs, use RAG, or verify companies/domains. Those are separate, later stages.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import pytesseract

from ._extractors import extract_all

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

# Maximum size for uploaded files (bytes). 10 MB is generous for images/PDFs
# while still guarding against abuse.
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024

# Maximum size for fetched web content (bytes).
MAX_WEB_CONTENT_BYTES: int = 5 * 1024 * 1024

# Timeout for outbound HTTP requests (seconds).
HTTP_TIMEOUT_SECONDS: float = 15.0

# Maximum number of redirects to follow.
MAX_REDIRECTS: int = 5

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """The type of input that was processed."""

    TEXT = "text"
    URL = "url"
    IMAGE = "image"
    PDF = "pdf"


@dataclass
class InvestigationInput:
    """Standardized internal representation of a processed input.

    All downstream investigation nodes consume this object. It carries the
    original input, the extracted text, and the deterministic entity mentions
    found within it, along with provenance and diagnostic metadata.

    Entity fields contain *mentions* only. They are not verified facts.
    """

    source_type: SourceType
    raw_text: str
    extracted_text: str
    urls: list[str] = field(default_factory=list)
    email_addresses: list[str] = field(default_factory=list)
    phone_numbers: list[str] = field(default_factory=list)
    company_names: list[str] = field(default_factory=list)
    recruiter_names: list[str] = field(default_factory=list)
    job_titles: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    salary_mentions: list[str] = field(default_factory=list)
    file_name: Optional[str] = None
    processing_warnings: list[str] = field(default_factory=list)
    extraction_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return {
            "source_type": self.source_type.value,
            "raw_text": self.raw_text,
            "extracted_text": self.extracted_text,
            "urls": self.urls,
            "email_addresses": self.email_addresses,
            "phone_numbers": self.phone_numbers,
            "company_names": self.company_names,
            "recruiter_names": self.recruiter_names,
            "job_titles": self.job_titles,
            "locations": self.locations,
            "salary_mentions": self.salary_mentions,
            "file_name": self.file_name,
            "processing_warnings": self.processing_warnings,
            "extraction_metadata": self.extraction_metadata,
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def process_input(
    *,
    text: Optional[str] = None,
    url: Optional[str] = None,
    file_path: Optional[str | Path] = None,
    file_bytes: Optional[bytes] = None,
    file_name: Optional[str] = None,
) -> InvestigationInput:
    """Process a single input into a standardized ``InvestigationInput``.

    Exactly one of ``text``, ``url``, or ``file_path``/``file_bytes`` must be
    provided.

    Args:
        text: Plain text to process.
        url: A job posting URL to fetch and process.
        file_path: Path to an image or PDF file.
        file_bytes: Raw bytes of an image or PDF file (with ``file_name``).
        file_name: Name of the file when ``file_bytes`` is used.

    Returns:
        A populated ``InvestigationInput``.

    Raises:
        ValueError: If no input is provided, or if multiple inputs are given.
    """
    provided = [x is not None for x in (text, url, file_path, file_bytes)]
    if sum(provided) != 1:
        raise ValueError(
            "Exactly one of text, url, file_path, or file_bytes must be provided."
        )

    if text is not None:
        return _process_text(text)
    if url is not None:
        return _process_url(url)
    if file_path is not None:
        return _process_file(Path(file_path))
    # file_bytes is not None here
    if file_name is None:
        raise ValueError("file_name is required when file_bytes is provided.")
    return _process_file_bytes(file_bytes, file_name)


# ---------------------------------------------------------------------------
# Text processing
# ---------------------------------------------------------------------------


def _process_text(text: str) -> InvestigationInput:
    """Process plain text input."""
    if not text or not text.strip():
        raise ValueError("Input text is empty.")

    entities = extract_all(text)
    return InvestigationInput(
        source_type=SourceType.TEXT,
        raw_text=text,
        extracted_text=text,
        urls=entities["urls"],
        email_addresses=entities["email_addresses"],
        phone_numbers=entities["phone_numbers"],
        company_names=entities["company_names"],
        recruiter_names=entities["recruiter_names"],
        job_titles=entities["job_titles"],
        locations=entities["locations"],
        salary_mentions=entities["salary_mentions"],
        extraction_metadata={"extractor": "regex", "version": 1},
    )


# ---------------------------------------------------------------------------
# URL processing
# ---------------------------------------------------------------------------


def _process_url(url: str) -> InvestigationInput:
    """Fetch and process a job posting URL."""
    warnings: list[str] = []
    metadata: dict[str, Any] = {}

    if not _is_valid_http_url(url):
        raise ValueError(f"Invalid URL: {url!r}")

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - defensive
        raise RuntimeError("httpx is required for URL processing.") from exc

    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; JobScamDetector/1.0; "
                    "+https://example.invalid/bot)"
                )
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                warnings.append(
                    f"Unexpected content type {content_type!r}; treating as HTML."
                )
            if len(response.content) > MAX_WEB_CONTENT_BYTES:
                warnings.append("Web content exceeded size limit; truncated.")
            html = response.text[:MAX_WEB_CONTENT_BYTES]
            final_url = str(response.url)
            metadata["final_url"] = final_url
            metadata["status_code"] = response.status_code
            metadata["content_type"] = content_type
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Failed to fetch URL (HTTP {exc.response.status_code}): {url}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Timed out fetching URL: {url}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Request error fetching URL: {url} ({exc})") from exc

    extracted_text = _html_to_text(html)
    if not extracted_text.strip():
        warnings.append("No meaningful text extracted from the page.")

    entities = extract_all(extracted_text)
    return InvestigationInput(
        source_type=SourceType.URL,
        raw_text=url,
        extracted_text=extracted_text,
        urls=entities["urls"],
        email_addresses=entities["email_addresses"],
        phone_numbers=entities["phone_numbers"],
        company_names=entities["company_names"],
        recruiter_names=entities["recruiter_names"],
        job_titles=entities["job_titles"],
        locations=entities["locations"],
        salary_mentions=entities["salary_mentions"],
        processing_warnings=warnings,
        extraction_metadata=metadata,
    )


def _is_valid_http_url(url: str) -> bool:
    """Return True if ``url`` is a well-formed http/https URL."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _html_to_text(html: str) -> str:
    """Extract meaningful visible text from HTML, removing navigation noise."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover - defensive
        raise RuntimeError("beautifulsoup4 is required for URL processing.") from exc

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements that add noise.
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse blank lines and strip each line.
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned


# ---------------------------------------------------------------------------
# File processing (images & PDFs)
# ---------------------------------------------------------------------------


def _process_file(path: Path) -> InvestigationInput:
    """Process an image or PDF file from disk."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File too large ({file_size} bytes); max is {MAX_FILE_SIZE_BYTES} bytes."
        )

    data = path.read_bytes()
    return _process_file_bytes(data, path.name)


def _process_file_bytes(data: bytes, file_name: str) -> InvestigationInput:
    """Process raw image or PDF bytes."""
    if not data:
        raise ValueError("File is empty.")

    if len(data) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File too large ({len(data)} bytes); max is {MAX_FILE_SIZE_BYTES} bytes."
        )

    file_type = _detect_file_type(data, file_name)

    if file_type == "image":
        return _process_image(data, file_name)
    if file_type == "pdf":
        return _process_pdf(data, file_name)
    raise ValueError(f"Unsupported file type: {file_name!r}")


def _detect_file_type(data: bytes, file_name: str) -> str:
    """Detect whether the bytes are an image or a PDF.

    Uses magic bytes first, falling back to the file extension.
    """
    # PDF magic: "%PDF"
    if data[:4] == b"%PDF":
        return "pdf"

    # Image magic bytes.
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"
    if data[:3] == b"\xff\xd8\xff":  # JPEG
        return "image"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image"

    # Fall back to extension.
    ext = Path(file_name).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if ext == ".pdf":
        return "pdf"
    return "unknown"


# ---------------------------------------------------------------------------
# Image processing (OCR)
# ---------------------------------------------------------------------------


def _process_image(data: bytes, file_name: str) -> InvestigationInput:
    """Extract text from an image via OCR."""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"file_name": file_name}

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - defensive
        raise RuntimeError("Pillow is required for image processing.") from exc

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        metadata["format"] = image.format
        metadata["size"] = {"width": image.width, "height": image.height}
        metadata["mode"] = image.mode
    except Exception as exc:
        raise ValueError(f"Could not read image file {file_name!r}: {exc}") from exc

    ocr_text, ocr_meta = _run_ocr(image, warnings)
    metadata["ocr"] = ocr_meta

    if not ocr_text.strip():
        warnings.append("OCR produced no text; the image may be blank or unreadable.")

    entities = extract_all(ocr_text)
    return InvestigationInput(
        source_type=SourceType.IMAGE,
        raw_text="",
        extracted_text=ocr_text,
        urls=entities["urls"],
        email_addresses=entities["email_addresses"],
        phone_numbers=entities["phone_numbers"],
        company_names=entities["company_names"],
        recruiter_names=entities["recruiter_names"],
        job_titles=entities["job_titles"],
        locations=entities["locations"],
        salary_mentions=entities["salary_mentions"],
        file_name=file_name,
        processing_warnings=warnings,
        extraction_metadata=metadata,
    )


def _run_ocr(image: Any, warnings: list[str]) -> tuple[str, dict[str, Any]]:
    """Run OCR on a PIL image.

    Uses pytesseract if available. Returns ``(text, metadata)``. If OCR is
    not available, returns an empty string with a warning rather than failing
    silently.
    """
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract-OCR\tesseract.exe"
    except ImportError:
        warnings.append(
            "OCR is not available (pytesseract not installed). "
            "Install pytesseract and the Tesseract binary to extract text from images."
        )
        return "", {"available": False}

    try:
        text = pytesseract.image_to_string(image)
        # pytesseract does not expose per-image confidence directly; record
        # that OCR ran successfully.
        return text, {"available": True, "engine": "tesseract"}
    except Exception as exc:
        warnings.append(f"OCR failed: {exc}")
        return "", {"available": True, "engine": "tesseract", "error": str(exc)}


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------


# def _process_pdf(data: bytes, file_name: str) -> InvestigationInput:
#     """Extract text from a PDF, detecting scanned/image PDFs."""
#     warnings: list[str] = []
#     metadata: dict[str, Any] = {"file_name": file_name}

#     try:
#         import fitz  # PyMuPDF
#     except ImportError as exc:  # pragma: no cover - defensive
#         raise RuntimeError("PyMuPDF is required for PDF processing.") from exc

#     try:
#         doc = fitz.open(stream=data, filetype="pdf")
#     except Exception as exc:
#         raise ValueError(f"Could not open PDF {file_name!r}: {exc}") from exc

#     if doc.needs_pass:
#         doc.close()
#         raise ValueError(f"PDF {file_name!r} is password-protected.")

#     metadata["page_count"] = doc.page_count

#     pages_text: list[str] = []
#     scanned_pages = 0
#     for page_num, page in enumerate(doc, start=1):
#         page_text = page.get_text("text").strip()
#         if not page_text:
#             scanned_pages += 1
#         pages_text.append(page_text)

#     doc.close()

#     extracted_text = "\n\n".join(pages_text).strip()

#     if scanned_pages > 0:
#         warnings.append(
#             f"{scanned_pages} of {metadata['page_count']} page(s) appear to be "
#             "scanned images with no embedded text. OCR is not applied to PDFs "
#             "in this version."
#         )
#         metadata["scanned_pages"] = scanned_pages

#     if not extracted_text:
#         warnings.append(
#             "No text could be extracted from the PDF. It may be a scanned "
#             "document or contain only images."
#         )

#     entities = extract_all(extracted_text)
#     return InvestigationInput(
#         source_type=SourceType.PDF,
#         raw_text="",
#         extracted_text=extracted_text,
#         urls=entities["urls"],
#         email_addresses=entities["email_addresses"],
#         phone_numbers=entities["phone_numbers"],
#         company_names=entities["company_names"],
#         recruiter_names=entities["recruiter_names"],
#         job_titles=entities["job_titles"],
#         locations=entities["locations"],
#         salary_mentions=entities["salary_mentions"],
#         file_name=file_name,
#         processing_warnings=warnings,
#         extraction_metadata=metadata,
#     )

def _process_pdf(data: bytes, file_name: str) -> InvestigationInput:
    """Extract text from a PDF, using OCR for scanned/image-only pages."""
    warnings: list[str] = []
    metadata: dict[str, Any] = {"file_name": file_name}

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - defensive
        raise RuntimeError("PyMuPDF is required for PDF processing.") from exc

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for PDF OCR.") from exc

    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = (
            r"D:\Tesseract-OCR\tesseract.exe"
        )
    except ImportError as exc:
        raise RuntimeError("pytesseract is required for PDF OCR.") from exc

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError(
            f"Could not open PDF {file_name!r}: {exc}"
        ) from exc

    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"PDF {file_name!r} is password-protected."
        )

    metadata["page_count"] = doc.page_count

    pages_text: list[str] = []
    scanned_pages = 0
    ocr_pages = 0

    for page_num, page in enumerate(doc, start=1):

        # ---------------------------------------------------------
        # 1. Try normal PDF text extraction first
        # ---------------------------------------------------------

        page_text = page.get_text("text").strip()

        if page_text:
            pages_text.append(page_text)
            continue

        # ---------------------------------------------------------
        # 2. No embedded text -> treat page as scanned/image PDF
        # ---------------------------------------------------------

        scanned_pages += 1

        try:
            # Render PDF page as an image
            pix = page.get_pixmap(
                dpi=200,
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            # Run the same Tesseract OCR used for image uploads
            ocr_text = pytesseract.image_to_string(
                image,
                config="--psm 6"
            ).strip()

            if ocr_text:
                pages_text.append(ocr_text)
                ocr_pages += 1
            else:
                pages_text.append("")

        except Exception as exc:
            pages_text.append("")

            warnings.append(
                f"OCR failed on page {page_num}: "
                f"{type(exc).__name__}: {exc}"
            )

    doc.close()

    # -------------------------------------------------------------
    # Build final extracted text
    # -------------------------------------------------------------

    extracted_text = "\n\n".join(
        text for text in pages_text if text
    ).strip()

    metadata["scanned_pages"] = scanned_pages
    metadata["ocr_pages"] = ocr_pages

    if scanned_pages > 0:

        if ocr_pages > 0:
            warnings.append(
                f"{scanned_pages} page(s) had no embedded text; "
                f"OCR successfully extracted text from "
                f"{ocr_pages} page(s)."
            )
        else:
            warnings.append(
                f"{scanned_pages} page(s) had no embedded text "
                "and OCR did not produce usable text."
            )

    if not extracted_text:
        warnings.append(
            "No text could be extracted from the PDF. "
            "The document may be blank, unreadable, or unsupported."
        )

    # -------------------------------------------------------------
    # Entity extraction
    # -------------------------------------------------------------

    entities = extract_all(extracted_text)

    return InvestigationInput(
        source_type=SourceType.PDF,
        raw_text="",
        extracted_text=extracted_text,
        urls=entities["urls"],
        email_addresses=entities["email_addresses"],
        phone_numbers=entities["phone_numbers"],
        company_names=entities["company_names"],
        recruiter_names=entities["recruiter_names"],
        job_titles=entities["job_titles"],
        locations=entities["locations"],
        salary_mentions=entities["salary_mentions"],
        file_name=file_name,
        processing_warnings=warnings,
        extraction_metadata=metadata,
    )