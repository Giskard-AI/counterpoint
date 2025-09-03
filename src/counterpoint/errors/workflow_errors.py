class WorkflowError(RuntimeError):
    """An error that occurs during a workflow."""


class ToolCallError(WorkflowError):
    """An error that occurs during a tool call."""
