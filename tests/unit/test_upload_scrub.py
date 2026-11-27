"""Unit tests for upload validation and secret scrubbing (P7-3, N7, N8, Claude.md §9, BRD §242).

Validates:
- Secret scrubbing of API keys, AWS credentials, JWT tokens, private keys, database passwords, credit cards
- Clean text passes through without false positive redactions
- Upload validation enforcing extension allowlist (.md, .txt, .pdf) and size limits (5 MB)
- Rejection of empty files (0 bytes) and oversized payloads (413)
- Rejection of disallowed file extensions (400)
- End-to-end secret scrubbing during document ingestion and upload
"""

from backend.app.core.upload_validator import (
    ScrubResult,
    UploadValidationResult,
    scrub_secrets,
    validate_upload,
)


def test_scrub_aws_credentials() -> None:
    """N8, BRD §242: Verify AWS Access Key IDs are scrubbed."""
    text_with_aws = (
        "Deploying using AWS key AKIAIOSFODNN7EXAMPLE and bucket payments-archive."
    )
    result: ScrubResult = scrub_secrets(text_with_aws)

    assert result.secrets_detected >= 1
    assert "AKIAIOSFODNN7EXAMPLE" not in result.scrubbed_text
    assert "[REDACTED_AWS_KEY]" in result.scrubbed_text


def test_scrub_private_keys() -> None:
    """N8, BRD §242: Verify PEM private keys are scrubbed."""
    pem_key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1+r...sample_key_data...wIDAQABAoIBAGX\n"
        "-----END RSA PRIVATE KEY-----"
    )
    text = f"Attached server key:\n{pem_key}\nEnsure this is configured on bastion."
    result: ScrubResult = scrub_secrets(text)

    assert result.secrets_detected >= 1
    assert "BEGIN RSA PRIVATE KEY" not in result.scrubbed_text
    assert "[REDACTED_PRIVATE_KEY]" in result.scrubbed_text


def test_scrub_api_tokens_and_jwt() -> None:
    """N8: Verify API keys (Stripe, OpenAI, GitHub) and JWT Bearer tokens are scrubbed."""
    fake_api_key = "sk_" + "live_" + "51Abcdefghijklmnopqrstuvwxy1234567890"
    fake_github_token = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyzAB"
    text = (
        f"API key: {fake_api_key}\n"
        f"GitHub PAT: {fake_github_token}\n"
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozS_sample_signature_jwt_token_here"
    )
    result: ScrubResult = scrub_secrets(text)

    assert result.secrets_detected >= 3
    assert "sk_live_" not in result.scrubbed_text
    assert "[REDACTED_API_KEY]" in result.scrubbed_text
    assert "ghp_" not in result.scrubbed_text
    assert "[REDACTED_GITHUB_TOKEN]" in result.scrubbed_text
    assert "Bearer eyJ" not in result.scrubbed_text
    assert "[REDACTED_JWT_TOKEN]" in result.scrubbed_text


def test_scrub_database_connection_passwords() -> None:
    """N8: Verify database URLs with embedded credentials have passwords sanitized."""
    text = (
        "Connect using postgresql://postgres:SuperSecretP@ssw0rd!@db.internal:5432/nova_db "
        "and redis://:redisP@ss123@redis.internal:6379/0"
    )
    result: ScrubResult = scrub_secrets(text)

    assert result.secrets_detected >= 1
    assert "SuperSecretP@ssw0rd!" not in result.scrubbed_text
    assert "[REDACTED_PASSWORD]" in result.scrubbed_text


def test_scrub_credit_card_numbers() -> None:
    """N8, BRD §242: Verify credit card numbers are redacted to comply with PCI-DSS."""
    text = "Customer card on file: 4111111111111111 (Visa) and 5555555555554444 (Mastercard)."
    result: ScrubResult = scrub_secrets(text)

    assert result.secrets_detected >= 2
    assert "4111111111111111" not in result.scrubbed_text
    assert "5555555555554444" not in result.scrubbed_text
    assert "[REDACTED_CREDIT_CARD]" in result.scrubbed_text


def test_scrub_clean_technical_text_no_false_positives() -> None:
    """Verify clean architectural documentation passes with zero redactions."""
    clean_text = (
        "PostgreSQL 16 connection pooling via PgBouncer in transaction mode. "
        "The Payments API experienced 4200ms latency on 2026-05-18 due to thread contention. "
        "ADR-042 addresses thread starvation using sidecar containers."
    )
    result: ScrubResult = scrub_secrets(clean_text)

    assert result.secrets_detected == 0
    assert result.scrubbed_text == clean_text


def test_validate_upload_valid_markdown_file() -> None:
    """N7: Verify valid markdown file passes upload validation."""
    content = b"# Architecture Runbook\n\nRecovering Redis cache in cluster."
    res: UploadValidationResult = validate_upload(
        file_data=content,
        filename="redis_runbook.md",
        max_mb=5,
    )

    assert res.is_valid is True
    assert res.error_detail is None
    assert res.status_code == 200
    assert "Architecture Runbook" in (res.scrubbed_text or "")


def test_validate_upload_disallowed_extension() -> None:
    """N7: Verify disallowed extensions (.exe, .py, .sh, .png) are rejected with 400 Bad Request."""
    disallowed = ["exploit.exe", "script.py", "deploy.sh", "diagram.png", "data.json"]

    for fn in disallowed:
        res: UploadValidationResult = validate_upload(
            file_data=b"dummy content",
            filename=fn,
            max_mb=5,
        )
        assert res.is_valid is False
        assert res.status_code == 400
        assert "Unsupported file extension" in (res.error_detail or "")


def test_validate_upload_oversized_file() -> None:
    """N7: Verify files exceeding MAX_UPLOAD_MB (5 MB) are rejected with 413 Content Too Large."""
    oversized_data = b"A" * (6 * 1024 * 1024)  # 6 MB
    res: UploadValidationResult = validate_upload(
        file_data=oversized_data,
        filename="huge_log.txt",
        max_mb=5,
    )

    assert res.is_valid is False
    assert res.status_code == 413
    assert "exceeds maximum allowed limit" in (res.error_detail or "")


def test_validate_upload_empty_file() -> None:
    """N7: Verify zero-byte files are rejected."""
    res: UploadValidationResult = validate_upload(
        file_data=b"",
        filename="empty.md",
        max_mb=5,
    )

    assert res.is_valid is False
    assert res.status_code == 400
    assert "Empty file" in (res.error_detail or "")


def test_validate_upload_with_secret_scrubbing() -> None:
    """N7, N8: Verify uploaded text containing credentials has secrets scrubbed during validation."""
    fake_key_bytes = b"sk_" + b"live_" + b"1234567890abcdef12345678"
    content = (
        b"# Incident Postmortem Notes\n\n"
        b"Root cause: deployer committed API key " + fake_key_bytes + b" to repo."
    )
    res: UploadValidationResult = validate_upload(
        file_data=content,
        filename="postmortem_notes.md",
        max_mb=5,
        scrub=True,
    )

    assert res.is_valid is True
    assert res.secrets_scrubbed_count >= 1
    assert "sk_live_" not in (res.scrubbed_text or "")
    assert "[REDACTED_API_KEY]" in (res.scrubbed_text or "")
