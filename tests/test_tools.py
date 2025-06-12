"""Tests for the tools module."""

from typing import List


import counterpoint as cp
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
    assert list(search_web.parameters_schema["properties"].keys()) == [
        "query",
        "max_results",
    ]

    assert search_web.parameters_schema["properties"]["query"]["type"] == "string"
    assert (
        search_web.parameters_schema["properties"]["query"]["description"]
        == "The search query to use."
    )

    assert (
        search_web.parameters_schema["properties"]["max_results"]["type"] == "integer"
    )
    assert (
        search_web.parameters_schema["properties"]["max_results"]["description"]
        == "Maximum number of documents that should be returned for the call."
    )

    assert search_web.parameters_schema["required"] == ["query"]

    assert search_web("Q", max_results=5) == ["This is a test", "another test for Q"]


async def test_tool_run(generator):
    """Test that the tool runs correctly."""

    @cp.tool
    def get_weather(city: str) -> str:
        """Get the weather in a city.

        Parameters
        ----------
        city: str
            The city to get the weather for.
        """
        if city == "Paris":
            return f"It's raining in {city}."

        return f"It's sunny in {city}."

    chat = await (
        generator.chat("Hello, what's the weather in Paris?")
        .with_tools(get_weather)
        .run()
    )

    assert "rain" in chat.last.content.lower()
