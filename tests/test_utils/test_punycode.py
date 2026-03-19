"""Tests for power_scrapper.utils.punycode."""

from __future__ import annotations

from power_scrapper.utils.punycode import PunycodeDecoder


class TestPunycodeDecoder:
    def test_decode_russian_domain(self) -> None:
        # xn--e1afmkfd.xn--p1ai == "пример.рф"
        result = PunycodeDecoder.decode_domain("xn--e1afmkfd.xn--p1ai")
        assert result == "пример.рф"

    def test_non_punycode_unchanged(self) -> None:
        assert PunycodeDecoder.decode_domain("example.com") == "example.com"

    def test_mixed_labels(self) -> None:
        # Only the xn-- part should be decoded.
        result = PunycodeDecoder.decode_domain("subdomain.xn--p1ai")
        assert result == "subdomain.рф"

    def test_empty_string(self) -> None:
        assert PunycodeDecoder.decode_domain("") == ""

    def test_single_label_no_dots(self) -> None:
        assert PunycodeDecoder.decode_domain("localhost") == "localhost"

    def test_invalid_punycode_returns_original(self) -> None:
        # xn--zzzzzzzzzzzz is not a valid Punycode label.
        result = PunycodeDecoder.decode_domain("xn--zzzzzzzzzzzzzzzzzzzzzzzz.com")
        # Should fall back to the original label instead of crashing.
        assert ".com" in result
