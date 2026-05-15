"""Thin jmespath wrapper for OLX Cars actor.

Provides a simple interface for extracting values from JSON objects
using JMESPath expressions.
"""

from __future__ import annotations

import jmespath


class Jmes:
    """Wrapper around jmespath for convenient data extraction."""

    def __init__(self, data: dict | list) -> None:
        """Initialise with a parsed Python object (dict or list)."""
        self._data = data

    def select(self, expression: str, default=None):
        """Extract a scalar value using a JMESPath expression.

        Returns ``default`` when the expression matches nothing or returns
        an empty string.
        """
        result = jmespath.search(expression, self._data)
        if result is None or result == '':
            return default
        if isinstance(result, list):
            return result
        return str(result)

    def select_list(self, expression: str, default: list | None = None) -> list:
        """Extract a list value using a JMESPath expression.

        Always returns a list.  Returns ``default`` (empty list when None)
        when the expression matches nothing.
        """
        if default is None:
            default = []
        result = jmespath.search(expression, self._data)
        if result is None or result == '':
            return default
        if isinstance(result, list):
            return result
        return [result]

    def select_dict(self, expression: str, default: dict | None = None) -> dict:
        """Extract a dict value using a JMESPath expression.

        Returns ``default`` (empty dict when None) when the expression
        matches nothing or the result is not a dict.
        """
        if default is None:
            default = {}
        result = jmespath.search(expression, self._data)
        if result is None or result == '':
            return default
        if isinstance(result, dict):
            return result
        return default
