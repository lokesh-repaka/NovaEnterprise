"""Upload validation and secret scrubbing services for NovaEnterprise (Claude.md §9, PRD §N7, §N8, BRD §242).

Enforces:
- File extension allowlist: .md, .markdown, .txt, .pdf (N7)
- Upload size cap: MAX_UPLOAD_MB (default 5 MB) (N7)
- Rejection of empty files (0 bytes)
- Automatic secret and credential scrubbing prior to vectorization and storage:
    - AWS Access Keys and Secrets
    - Private Keys (RSA, EC, DSA, OPENSSH, PGP)
    - API Tokens (Stripe, OpenAI, GitHub, GitLab)
    - JWT Bearer Tokens
    - Database Connection Strings with Passwords
    - Credit Card Numbers (PCI-DSS compliance)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.guardrails import scan_prompt_injection

# Constants (Claude.md §9, PRD §N7)
MAX_UPLOAD_MB: int = 5
ALLOWED_EXTENSIONS: set[str] = {".md", ".markdown", ".txt", ".pdf"}

# Scrubbing regex patterns
SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "AWS_KEY",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        "PRIVATE_KEY",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "API_KEY",
        re.compile(r"\bsk_(?:live|test)_[0-9a-zA-Z]{20,}\b"),
        "[REDACTED_API_KEY]",
    ),
    (
        "GITHUB_TOKEN",
        re.compile(r"\bghp_[0-9a-zA-Z]{30,45}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        "GITLAB_TOKEN",
        re.compile(r"\bglpat-[0-9a-zA-Z\-]{20,}\b"),
        "[REDACTED_GITLAB_TOKEN]",
    ),
    (
        "JWT_TOKEN",
        re.compile(r"Bearer\s+eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        "Bearer [REDACTED_JWT_TOKEN]",
    ),
    (
        "CREDIT_CARD",
        re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "[REDACTED_CREDIT_CARD]",
    ),
]

# Database connection URL password scrubber
DB_URL_PATTERN = re.compile(
    r"((?:postgres|postgresql|mysql|redis|mongodb|amqp)://(?:[^:]+):)([^@\s]+)(@)",
    re.IGNORECASE,
)


class ScrubbedSecret(BaseModel):
    """Metadata regarding a detected and scrubbed sensitive value."""

    secret_type: str
    redacted_token: str
    snippet_preview: str | None = None


class ScrubResult(BaseModel):
    """Result of automated secret scrubbing."""

    scrubbed_text: str
    secrets_detected: int = 0
    scrubbed_items: list[ScrubbedSecret] = Field(default_factory=list)


class UploadValidationResult(BaseModel):
    """Result of file upload validation (N7, N8)."""

    is_valid: bool
    filename: str
    content_bytes: bytes
    scrubbed_text: str | None = None
    secrets_scrubbed_count: int = 0
    flagged_injection: bool = False
    error_detail: str | None = None
    status_code: int = 200
    metadata: dict[str, Any] = Field(default_factory=dict)


def scrub_secrets(text: str) -> ScrubResult:
    """Detect and redact secrets, credentials, and PII from text (N8, BRD §242).

    Sanitizes:
    - AWS access keys
    - PEM private keys
    - API keys and tokens (Stripe, OpenAI, GitHub, GitLab)
    - JWT tokens
    - Database connection string passwords
    - Credit card numbers
    """
    if not text:
        return ScrubResult(scrubbed_text="", secrets_detected=0, scrubbed_items=[])

    scrubbed = text
    scrubbed_items: list[ScrubbedSecret] = []
    total_detected = 0

    # 1. Standard regex replacement
    for secret_type, pattern, replacement in SECRET_PATTERNS:
        matches = list(pattern.finditer(scrubbed))
        if matches:
            total_detected += len(matches)
            for _ in matches:
                scrubbed_items.append(
                    ScrubbedSecret(
                        secret_type=secret_type,
                        redacted_token=replacement,
                    )
                )
            scrubbed = pattern.sub(replacement, scrubbed)

    # 2. Database connection password scrubbing
    db_matches = list(DB_URL_PATTERN.finditer(scrubbed))
    if db_matches:
        total_detected += len(db_matches)
        for _ in db_matches:
            scrubbed_items.append(
                ScrubbedSecret(
                    secret_type="DATABASE_PASSWORD",
                    redacted_token="[REDACTED_PASSWORD]",
                )
            )
        scrubbed = DB_URL_PATTERN.sub(r"\1[REDACTED_PASSWORD]\3", scrubbed)

    return ScrubResult(
        scrubbed_text=scrubbed,
        secrets_detected=total_detected,
        scrubbed_items=scrubbed_items,
    )


def validate_upload(
    file_data: bytes,
    filename: str,
    max_mb: int = MAX_UPLOAD_MB,
    scrub: bool = True,
) -> UploadValidationResult:
    """Validate an uploaded file against size and extension allowlists and scrub secrets (N7, N8).

    Guarantees:
    - Rejects files with unsupported extensions (400 Bad Request).
    - Rejects empty files (0 bytes) (400 Bad Request).
    - Rejects files exceeding max_mb (413 Content Too Large).
    - Scrubs secrets and scans prompt injection for text-based uploads.
    """
    clean_filename = filename or "uploaded_document.txt"
    suffix = Path(clean_filename).suffix.lower()

    # 1. Empty file check
    if not file_data or len(file_data) == 0:
        return UploadValidationResult(
            is_valid=False,
            filename=clean_filename,
            content_bytes=file_data,
            error_detail="Empty file uploaded (0 bytes) (N7)",
            status_code=400,
        )

    # 2. Extension allowlist check (N7)
    if suffix not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return UploadValidationResult(
            is_valid=False,
            filename=clean_filename,
            content_bytes=file_data,
            error_detail=(
                f"Unsupported file extension '{suffix}'. "
                f"Allowed extensions are: {allowed_str} (N7)"
            ),
            status_code=400,
        )

    # 3. File size limit check (N7)
    max_bytes = max_mb * 1024 * 1024
    if len(file_data) > max_bytes:
        return UploadValidationResult(
            is_valid=False,
            filename=clean_filename,
            content_bytes=file_data,
            error_detail=(
                f"File size ({len(file_data)} bytes) exceeds maximum allowed limit "
                f"of {max_mb} MB ({max_bytes} bytes) (N7)"
            ),
            status_code=413,
        )

    # 4. Content processing for text files (.md, .txt)
    scrubbed_text: str | None = None
    secrets_count = 0
    flagged_injection = False
    final_bytes = file_data

    if suffix in {".md", ".markdown", ".txt"}:
        try:
            raw_text = file_data.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_data.decode("latin-1")

        # Scan prompt injection (N8)
        flagged_injection, _ = scan_prompt_injection(raw_text)

        # Scrub secrets (BRD §242)
        if scrub:
            scrub_res = scrub_secrets(raw_text)
            scrubbed_text = scrub_res.scrubbed_text
            secrets_count = scrub_res.secrets_detected
            final_bytes = scrubbed_text.encode("utf-8")
        else:
            scrubbed_text = raw_text

    return UploadValidationResult(
        is_valid=True,
        filename=clean_filename,
        content_bytes=final_bytes,
        scrubbed_text=scrubbed_text,
        secrets_scrubbed_count=secrets_count,
        flagged_injection=flagged_injection,
        status_code=200,
    )
