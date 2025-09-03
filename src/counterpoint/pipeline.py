"""Exporting the old Pipeline class for backwards compatibility."""

from counterpoint.workflow import ChatWorkflow as Pipeline


__all__ = ["Pipeline"]
