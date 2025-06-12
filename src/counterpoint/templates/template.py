from typing import Any
from pydantic import BaseModel
from jinja2 import Environment, StrictUndefined

from counterpoint.chat import Role, Message


_env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
    autoescape=False,
)


class MessageTemplate(BaseModel):
    role: Role
    content_template: str

    def render(self, **kwargs: Any) -> Message:
        """
        Render the message template with the given context.
        """
        template = _env.from_string(self.content_template)
        rendered_content = template.render(**kwargs)

        return Message(role=self.role, content=rendered_content)
