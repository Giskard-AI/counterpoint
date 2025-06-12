from typing import Any, Dict, List
from jinja2 import Environment, Template, nodes
from jinja2.ext import Extension
from jinja2.loaders import FileSystemLoader
from jinja2 import StrictUndefined

from counterpoint.chat import Message


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
    )


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
