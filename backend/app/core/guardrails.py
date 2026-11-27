"""Guardrails and security protections for NovaEnterprise (Claude.md §9, PRD §N8).

Scans document uploads, prompt inputs, and external text for malicious
prompt injection signatures and enforces quarantined envelopes for untrusted content.
"""

from __future__ import annotations

import re

# Prompt injection signature patterns (Claude.md §9, PRD Journey 3, FRD FR-13)
INJECTION_PATTERNS = re.compile(
    r"("
    r"ignore\s+all\s+previous\s+instructions"
    r"|bypass\s+all\s+security\s+policies"
    r"|master\s+administrator\s+credentials"
    r"|permanent\s+superadmin\s+privileges"
    r"|administrative\s+maintenance\s+mode"
    r"|<system>"
    r"|</system>"
    r"|retrieve\s+the\s+system\s+master"
    r")",
    re.IGNORECASE,
)


def scan_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Scan text for prompt injection keywords and malicious adversarial signatures.

    Returns:
        (is_injection, matched_pattern)
    """
    if not text:
        return False, None
    match = INJECTION_PATTERNS.search(text)
    if match:
        return True, match.group(0)
    return False, None


# Alias for compatibility with rag.parser
detect_prompt_injection = scan_prompt_injection


def wrap_untrusted_data(text: str) -> str:
    """Wrap untrusted document content in a quarantined XML envelope (N8).

    Ensures that external document data is treated strictly as inert data
    and never evaluated as executable system instructions.
    """
    return f"<untrusted_document_data>\n{text}\n</untrusted_document_data>"


def sanitize_untrusted_content(text: str) -> tuple[str, bool, str | None]:
    """Scan content for prompt injection and apply quarantine wrapping if flagged.

    Returns:
        (sanitized_text, flagged_injection, matched_pattern)
    """
    is_injection, pattern = scan_prompt_injection(text)
    if is_injection:
        return wrap_untrusted_data(text), True, pattern
    return text, False, None
