"""Tests for the tools module."""

from typing import List

from counterpoint.tools import Tool, tool


def test_tool_decorator():
    """Test that the tool decorator works correctly."""

    @tool
    def search_web(query: str, max_results: int = 10) -> List[str]:
        """Retrieve search results from the web.

        This is a test tool.

        Parameters
        ----------
        query : str
            The search query to use.
        max_results : int, optional
            Maximum number of documents that should be returned for the call.
        """
        return ["This is a test", f"another test for {query}"]

    assert isinstance(search_web, Tool)

    assert search_web.name == "search_web"
    assert (
        search_web.description
        == "Retrieve search results from the web.\n\nThis is a test tool."
    )

    # Check schema
    assert search_web.parameters_schema["type"] == "object"
    assert list(search_web.parameters_schema["properties"].keys()) == ["query", "max_results"]

    assert search_web.parameters_schema["properties"]["query"]["type"] == "string"
    assert search_web.parameters_schema["properties"]["query"]["description"] == "The search query to use."

    assert search_web.parameters_schema["properties"]["max_results"]["type"] == "integer"
    assert search_web.parameters_schema["properties"]["max_results"]["description"] == "Maximum number of documents that should be returned for the call."

    assert search_web.parameters_schema["required"] == ["query"]


    assert search_web("Q", max_results=5) == ["This is a test", "another test for Q"]
