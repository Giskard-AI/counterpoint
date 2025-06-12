from pathlib import Path
from typing import List, Dict, Any

from counterpoint.chat import Message
from .message_parser import create_message_environment, render_messages_template


class PromptsManager:
    """Manages prompts path and template loading."""

    def __init__(self, path: Path | None = None):
        self._prompts_path: Path = path or Path.cwd() / "prompts"

    def set_prompts_path(self, path: str):
        """Set a custom prompts path."""
        self._prompts_path = Path(path)

    def get_prompts_path(self) -> Path:
        """Get the current prompts path."""
        return self._prompts_path

    async def render_template(
        self, template_name: str, variables: Dict[str, Any] = None
    ) -> List[Message]:
        """
        Load and parse a template file, returning a list of Message objects.

        Parameters
        ----------
        template_name : str
            The template name
        variables : Dict[str, Any], optional
            Variables to pass to the template for rendering

        Returns
        -------
        List[Message]
            List of parsed Message objects
        """
        # We create a fresh environment for each render to isolate the state
        # between renders. This is slightly inefficient but necessary for the
        # message parser to work correctly.
        env = create_message_environment(str(self._prompts_path))
        template = env.get_template(template_name)

        messages = await render_messages_template(template, variables)

        return messages


# Global instance
_prompts_manager = PromptsManager()


def set_prompts_path(path: str):
    """Set a custom prompts path."""
    _prompts_manager.set_prompts_path(path)


def get_prompts_path() -> Path:
    """Get the current prompts path."""
    return _prompts_manager.get_prompts_path()


async def render_template(
    template_name: str, variables: Dict[str, Any] = None
) -> list[Message]:
    """Load and parse a template file."""
    return await _prompts_manager.render_template(template_name, variables)
