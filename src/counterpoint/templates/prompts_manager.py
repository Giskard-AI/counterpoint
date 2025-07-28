import warnings
import importlib
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template
from pydantic import BaseModel, Field

from counterpoint.chat import Message

from .environment import create_message_environment


async def render_messages_template(
    template: Template, variables: Dict[str, Any] = None
) -> List[Message]:
    """
    Render a template and collect any messages defined with {% message %} blocks.

    Parameters
    ----------
    template : Template
        The Jinja2 template to render
    variables : Dict[str, Any], optional
        Variables to pass to the template

    Returns
    -------
    List[Message]
        List of parsed Message objects
    """
    rendered_output = await template.render_async(variables or {})
    messages = template.environment._collected_messages

    # Two cases here:
    # 1. There are message blocks. In this case, the render output must be empty (at most whitespaces).
    # 2. There are no message blocks. In this case, we will create a single user message with the rendered output.
    if messages:
        if rendered_output.strip():
            raise ValueError(
                "Template contains message blocks but rendered output is not empty."
            )
        return messages
    else:
        return [Message(role="user", content=rendered_output)]


class PromptsManager(BaseModel):
    """Manages prompts path and template loading."""

    prompts_path: Path = Field(default_factory=lambda: Path.cwd() / "prompts")
    prompts_sources: Dict[str, Path] = Field(default_factory=dict)
    _lock: threading.RLock = Field(default_factory=threading.RLock, exclude=True)

    def register_prompts_source(self, source: str, namespace: str):
        """Register a prompts source.
        
        Parameters
        ----------
        source : str
            The source name
        namespace : str
            The namespace to use for the source
        """
        with self._lock: # Locking is necessary to avoid race conditions
            if namespace in self.prompts_sources:
                warnings.warn(f"Prompt source {namespace} already registered")

            self.prompts_sources[namespace] = Path(source)

    def set_prompts_path(self, path: str | Path):
        """Set a custom prompts path."""
        self.prompts_path = Path(path)

    def _resolve_package_namespace(self, namespace: str) -> Optional[Path]:
        """
        Automatically resolve a namespace to a package's prompts directory.
        
        Parameters
        ----------
        namespace : str
            The namespace/package name to resolve
            
        Returns
        -------
        Optional[Path]
            Path to the prompts directory if found, None otherwise
        """
        try:
            # Try to import the package
            module = importlib.import_module(namespace)
            
            # Get the package's root directory
            if hasattr(module, '__file__') and module.__file__:
                # For regular modules, go up to the package root
                package_root = Path(module.__file__).parent
                
                # If this is a file (not a directory), go up one more level
                if package_root.is_file():
                    package_root = package_root.parent
                    
                # Look for the prompts directory
                prompts_path = package_root / "prompts"
                if prompts_path.exists() and prompts_path.is_dir():
                    return prompts_path
                    
        except ImportError:
            # Package not found
            warnings.warn(f"Package {namespace} not found")
            pass
        except Exception as e:
            # Other errors (permission, etc.)
            warnings.warn(f"Error resolving package {namespace}: {e}")
            pass
            
        return None

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
        if "::" in template_name:
            namespace, template_name = template_name.split("::")
            
            # First check if explicitly registered
            with self._lock: # Locking is necessary to avoid race conditions
                if namespace in self.prompts_sources:
                    prompts_path = self.prompts_sources[namespace]
                else:
                    prompts_path = None
            
            if prompts_path is None:
                # Try to automatically resolve the package namespace
                prompts_path = self._resolve_package_namespace(namespace)
                if prompts_path is None:
                    raise ValueError(f"Prompt source {namespace} not registered and package not found")
        else:
            prompts_path = self.prompts_path

        # We create a fresh environment for each render to isolate the state
        # between renders. This is slightly inefficient but necessary for the
        # message parser to work correctly.
        env = create_message_environment(str(prompts_path))
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
