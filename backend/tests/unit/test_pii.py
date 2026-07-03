"""Unit tests for regex-based PII redaction."""

from __future__ import annotations

from context_engine.ingestion.pii import DEFAULT_PII_PATTERNS, REDACTED, redact


def test_emails_are_redacted() -> None:
    clean, hits = redact("reach me at liam@demo.dev or nina.p+test@demo.dev", DEFAULT_PII_PATTERNS)
    assert hits == 2
    assert "liam@demo.dev" not in clean
    assert "nina.p+test@demo.dev" not in clean
    assert clean.count(REDACTED) == 2


def test_phone_numbers_are_redacted() -> None:
    clean, hits = redact("call 415-555-0142 tomorrow", DEFAULT_PII_PATTERNS)
    assert hits == 1
    assert "415-555-0142" not in clean
    assert REDACTED in clean

    clean, hits = redact("cell +1 415 555 0142, office (415) 555-9000", DEFAULT_PII_PATTERNS)
    assert hits == 2
    assert "555 0142" not in clean
    assert "555-9000" not in clean


def test_aws_keys_are_redacted() -> None:
    clean, hits = redact("leaked key AKIAIOSFODNN7EXAMPLE in logs", DEFAULT_PII_PATTERNS)
    assert hits == 1
    assert "AKIA" not in clean


def test_no_match_returns_original_text_and_zero() -> None:
    text = "nothing sensitive in this sentence"
    assert redact(text, DEFAULT_PII_PATTERNS) == (text, 0)


def test_empty_pattern_list_is_a_noop() -> None:
    assert redact("liam@demo.dev", []) == ("liam@demo.dev", 0)


def test_custom_patterns() -> None:
    clean, hits = redact("card 4242424242424242 charged", [r"\b\d{16}\b"])
    assert clean == f"card {REDACTED} charged"
    assert hits == 1


def test_hits_sum_across_patterns() -> None:
    text = "liam@demo.dev leaked AKIAIOSFODNN7EXAMPLE and 415-555-0142"
    clean, hits = redact(text, DEFAULT_PII_PATTERNS)
    assert hits == 3
    assert clean.count(REDACTED) == 3
