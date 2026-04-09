"""Tests for app/security/input_sanitizer.py.

TC-U-001: sanitize() returns empty string for empty input.
TC-U-002: sanitize() removes zero-width Unicode characters.
TC-U-003: sanitize() removes control characters except newline, tab, space.
TC-U-004: sanitize() truncates text exceeding MAX_LEN (8000 chars).
TC-U-005: sanitize() preserves normal printable text unchanged.
TC-U-006: sanitize() preserves newlines and tabs.
TC-U-007: redact_pii() returns the input unchanged for empty string.
TC-U-008: redact_pii() replaces email addresses with <EMAIL>.
TC-U-009: redact_pii() replaces phone numbers with <PHONE>.
TC-U-010: redact_pii() replaces SSN patterns with <SSN>.
TC-U-011: redact_pii() replaces credit-card numbers with <CARD>.
TC-U-012: contains_credentials() returns False for empty input.
TC-U-013: contains_credentials() detects AWS access key (AKIA...).
TC-U-014: contains_credentials() detects GitHub personal token (ghp_...).
TC-U-015: contains_credentials() detects Bearer token header.
TC-U-015b: contains_credentials() detects PEM block (-----BEGIN).
TC-U-015c: apply_pii_layer() returns credential tag when credential present.
TC-U-015d: apply_pii_layer() redacts PII and returns no credential tag for clean PII text.
TC-U-015e: apply_pii_layer() returns empty credential tags for clean SRE text.
"""
from __future__ import annotations

import pytest

from app.security.input_sanitizer import (
    MAX_LEN,
    sanitize,
    redact_pii,
    contains_credentials,
)
from app.orchestration.agents.intake_guard.tools import apply_pii_layer


class TestSanitize:
    """TC-U-001 to TC-U-006: sanitize() layer."""

    def test_empty_string_returns_empty(self):
        """TC-U-001: sanitize() on empty string yields empty string."""
        assert sanitize("") == ""

    def test_removes_zero_width_characters(self):
        """TC-U-002: Zero-width Unicode chars are stripped."""
        text = "hello\u200bworld\u200c\u200d\ufeff"
        result = sanitize(text)
        assert "\u200b" not in result
        assert "\u200c" not in result
        assert "\u200d" not in result
        assert "\ufeff" not in result
        assert "helloworld" in result

    def test_removes_control_characters(self):
        """TC-U-003: Control chars other than \\n, \\t, space are stripped."""
        # \x01 is a control character, should be stripped
        text = "normal\x01text\x02here"
        result = sanitize(text)
        assert "\x01" not in result
        assert "\x02" not in result
        assert "normaltext" in result

    def test_truncates_at_max_len(self):
        """TC-U-004: Text longer than MAX_LEN is truncated."""
        long_text = "a" * (MAX_LEN + 500)
        result = sanitize(long_text)
        assert len(result) == MAX_LEN

    def test_preserves_normal_text(self):
        """TC-U-005: Normal ASCII printable text is preserved."""
        text = "CPU spike on ordering-service pod: 98% utilization"
        result = sanitize(text)
        assert result == text

    def test_preserves_newlines_and_tabs(self):
        """TC-U-006: Newline and tab characters are preserved (they are whitelisted)."""
        text = "line1\nline2\ttabbed"
        result = sanitize(text)
        assert "\n" in result
        assert "\t" in result


class TestRedactPii:
    """TC-U-007 to TC-U-011: redact_pii() replacements."""

    def test_empty_string_returned_as_is(self):
        """TC-U-007: Empty input returned unchanged (including falsy check)."""
        assert redact_pii("") == ""

    def test_redacts_email_address(self):
        """TC-U-008: Email address is replaced with <EMAIL> placeholder."""
        text = "Contact admin@company.com for details"
        result = redact_pii(text)
        assert "admin@company.com" not in result
        assert "<EMAIL>" in result

    def test_redacts_phone_number(self):
        """TC-U-009: Phone number is replaced with <PHONE> placeholder."""
        text = "Call me at 555-867-5309 to confirm"
        result = redact_pii(text)
        assert "555-867-5309" not in result
        assert "<PHONE>" in result

    def test_redacts_ssn(self):
        """TC-U-010: SSN pattern is replaced with <SSN> placeholder."""
        text = "User SSN: 123-45-6789 was found in logs"
        result = redact_pii(text)
        assert "123-45-6789" not in result
        assert "<SSN>" in result

    def test_redacts_credit_card(self):
        """TC-U-011: Credit card pattern is replaced with <CARD> placeholder."""
        text = "Card number 4111 1111 1111 1111 in payload"
        result = redact_pii(text)
        assert "4111 1111 1111 1111" not in result
        assert "<CARD>" in result

    def test_clean_sre_text_unchanged(self):
        """Legitimate SRE text should not be modified by redact_pii."""
        text = "The ordering service returned HTTP 502 after deploy v1.4.2"
        result = redact_pii(text)
        assert result == text

    def test_multiple_pii_types_all_redacted(self):
        """All PII types present in one string are all redacted."""
        text = "User john.doe@test.com called 555-123-4567 and SSN 987-65-4321"
        result = redact_pii(text)
        assert "<EMAIL>" in result
        assert "<PHONE>" in result
        assert "<SSN>" in result
        assert "john.doe@test.com" not in result
        assert "555-123-4567" not in result
        assert "987-65-4321" not in result


class TestContainsCredentials:
    """TC-U-012 to TC-U-015b: contains_credentials() detection."""

    def test_empty_string_returns_false(self):
        """TC-U-012: Empty string never contains credentials."""
        assert contains_credentials("") is False

    def test_detects_aws_access_key(self):
        """TC-U-013: AWS access key pattern (AKIA...) is detected."""
        text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE123456"
        assert contains_credentials(text) is True

    def test_detects_github_personal_token(self):
        """TC-U-014: GitHub personal token (ghp_...) is detected."""
        text = "token = ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        assert contains_credentials(text) is True

    def test_detects_bearer_token(self):
        """TC-U-015: Bearer token Authorization header is detected."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        assert contains_credentials(text) is True

    def test_detects_pem_block(self):
        """TC-U-015b: PEM block header is detected."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        assert contains_credentials(text) is True

    def test_clean_text_returns_false(self):
        """Normal SRE text without credentials returns False."""
        text = "Payment service pod crash-looping, Redis timeout 30s exceeded"
        assert contains_credentials(text) is False

    def test_none_equivalent_empty_returns_false(self):
        """Whitespace-only text does not match credential patterns."""
        assert contains_credentials("   ") is False


class TestApplyPiiLayer:
    """TC-U-015c to TC-U-015e: apply_pii_layer() integration."""

    def test_credential_text_returns_credential_tag(self):
        """TC-U-015c: Text with AWS key yields non-empty credential_tags."""
        text = "AWS key: AKIAIOSFODNN7EXAMPLE123456"
        redacted, credential_tags = apply_pii_layer(text)
        assert "credential" in credential_tags

    def test_pii_only_text_redacted_no_credential_tag(self):
        """TC-U-015d: Text with PII but no credentials is redacted, no credential tag."""
        text = "Reporter email admin@acme.com, SSN 123-45-6789"
        redacted, credential_tags = apply_pii_layer(text)
        # PII must be redacted
        assert "admin@acme.com" not in redacted
        assert "123-45-6789" not in redacted
        # Not a hard-block credential
        assert credential_tags == []

    def test_clean_text_returns_no_credential_tag(self):
        """TC-U-015e: Clean SRE text returns empty credential_tags."""
        text = "Catalog service returning 500 after latest deploy"
        redacted, credential_tags = apply_pii_layer(text)
        assert credential_tags == []
        assert redacted == text
