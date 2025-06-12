from pathlib import Path
from typing import List, Dict, Any

from pydantic import BaseModel, Field

from counterpoint.chat import Message
from .message_parser import create_message_environment, render_messages_template


class PromptsManager(BaseModel):
    """Manages prompts path and template loading."""

    prompts_path: Path = Field(default_factory=lambda: Path.cwd() / "prompts")

    def set_prompts_path(self, path: str | Path):
        """Set a custom prompts path."""
        self.prompts_path = Path(path)

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
        env = create_message_environment(str(self.prompts_path))
        template = env.get_template(template_name)

        messages = await render_messages_template(template, variables)

        return messages


# Global instance
_prompts_manager = PromptsManager()


def get_prompts_manager() -> PromptsManager:
    """Get the global prompts manager."""
    return _prompts_manager


def set_prompts_path(path: str):
    """Set a custom prompts path."""
    _prompts_manager.set_prompts_path(path)


async def render_template(
    template_name: str, variables: Dict[str, Any] = None
) -> list[Message]:
    """Load and parse a template file."""
    return await _prompts_manager.render_template(template_name, variables)
