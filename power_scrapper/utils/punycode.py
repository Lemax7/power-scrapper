"""Punycode / IDN domain decoding."""

from __future__ import annotations

import logging

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
