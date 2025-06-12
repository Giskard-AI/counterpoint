import json
from typing import Any

from jinja2 import Environment, StrictUndefined, nodes
from jinja2.ext import Extension
from jinja2.loaders import FileSystemLoader
from pydantic import BaseModel

from counterpoint.chat import Message


def _finalize_pydantic(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(), indent=4)
    return value


_inline_env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
    autoescape=False,
    finalize=_finalize_pydantic,
)


class MessageExtension(Extension):
    """Custom Jinja2 extension for parsing {% message role %}...{% endmessage %} blocks."""

    tags = {"message"}

    def __init__(self, environment):
        super().__init__(environment)
        if not hasattr(environment, "_collected_messages"):
            environment._collected_messages = []

    def parse(self, parser):
        """Parse a {% message role %}...{% endmessage %} block."""
        lineno = next(parser.stream).lineno
        role_node = parser.parse_expression()
        if isinstance(role_node, nodes.Name):
            role_node = nodes.Const(role_node.name)
        body = parser.parse_statements(["name:endmessage"], drop_needle=True)
        call_node = self.call_method("_handle_message", [role_node])

        return nodes.CallBlock(call_node, [], [], body).set_lineno(lineno)

    async def _handle_message(self, role: str, caller):
        """Handle a message block by rendering its content and storing it."""
        content = (await caller()).strip()
        self.environment._collected_messages.append(Message(role=role, content=content))
        return ""


def create_message_environment(prompts_path: str) -> Environment:
    """Create a Jinja2 environment with MessageExtension."""
    return Environment(
        loader=FileSystemLoader(prompts_path),
        extensions=[MessageExtension],
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
        autoescape=False,
        enable_async=True,
        finalize=_finalize_pydantic,
    )
