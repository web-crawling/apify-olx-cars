"""Regex helpers for OLX Cars actor."""

from __future__ import annotations

import re as _re


def first(pattern: str, text: str | None, flags: int = 0) -> str | None:
    """Return the first capture group matched by ``pattern`` in ``text``.

    Returns ``None`` when ``text`` is falsy or the pattern does not match.
    If the pattern has no capturing groups, returns the full match.
    """
    if not text:
        return None
    m = _re.search(pattern, text, flags)
    if m is None:
        return None
    groups = m.groups()
    if groups:
        return groups[0]
    return m.group(0)


def strip_html_tags(text: str | None) -> str:
    """Strip HTML tags and decode common HTML entities from a string.

    Used in the item loader for the ``description`` field which arrives
    with ``<br />`` and similar HTML markup from the OLX API.
    """
    if not text:
        return ''
    cleaned = _re.sub(r'<[^>]+>', ' ', text)
    cleaned = cleaned.replace('&lt;', '<')
    cleaned = cleaned.replace('&gt;', '>')
    cleaned = cleaned.replace('&amp;', '&')
    cleaned = cleaned.replace('&nbsp;', ' ')
    cleaned = cleaned.replace('&quot;', '"')
    cleaned = cleaned.replace('&#39;', "'")
    # Collapse multiple spaces / newlines
    cleaned = _re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = _re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()
