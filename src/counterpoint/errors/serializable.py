from pydantic import BaseModel


class Error(BaseModel):
    """A basic serializable error."""

    message: str
