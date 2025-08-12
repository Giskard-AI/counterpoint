"""Counterpoint-specific exception classes.

These exceptions provide clearer error semantics for configuration,
template, tool, parsing, and pipeline related issues compared to using
generic built-ins.
"""


class CounterpointError(Exception):
    """Base class for all Counterpoint errors."""


class CounterpointConfigError(CounterpointError):
    """Raised for invalid or missing configuration/state in Counterpoint."""


class ToolError(CounterpointError):
    """Base class for tool-related errors."""


class ToolDefinitionError(ToolError):
    """Raised when a tool is defined incorrectly (e.g., bad annotations)."""
