"""Punycode / IDN domain decoding and domain extraction utilities."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class PunycodeDecoder:
    """Decode Internationalized Domain Names (IDN) from Punycode (``xn--``) form."""

    @staticmethod
    def decode_domain(domain: str) -> str:
        """Decode a domain that may contain Punycode-encoded labels.

        Each dot-separated label starting with ``xn--`` is decoded using
        Python's ``idna`` codec.  Non-Punycode labels are left as-is.

        Parameters
        ----------
        domain:
            A domain name, e.g. ``"xn--e1afmapc.xn--p1ai"``.

        Returns
        -------
        str
            The decoded domain, e.g. ``"пример.рф"``.
        """
        parts = domain.split(".")
        decoded_parts: list[str] = []

        for part in parts:
            if part.startswith("xn--"):
                try:
                    decoded = part.encode("ascii").decode("idna")
                    decoded_parts.append(decoded)
                except (UnicodeError, UnicodeDecodeError) as exc:
                    logger.warning("Failed to decode Punycode label %r: %s", part, exc)
                    decoded_parts.append(part)
            else:
                decoded_parts.append(part)

        return ".".join(decoded_parts)


def extract_domain(url: str) -> str:
    """Extract the domain from *url* and decode any Punycode labels.

    Strips the port from the netloc so that ``"https://example.com:8080/path"``
    returns ``"example.com"`` (with Punycode labels decoded).

    Falls back to returning the original *url* on any parsing error.
    """
    try:
        netloc = urlparse(url).netloc
        # Strip port if present.
        host = netloc.split(":")[0] if netloc else ""
        if host:
            return PunycodeDecoder.decode_domain(host)
        return netloc
    except Exception:  # noqa: BLE001
        return url
