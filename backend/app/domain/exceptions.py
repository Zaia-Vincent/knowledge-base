"""Domain-specific exceptions — framework-independent."""


class EntityNotFoundError(Exception):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity_type: str, entity_id: int | str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id '{entity_id}' not found")


class DuplicateEntityError(Exception):
    """Raised when attempting to create a duplicate entity."""

    def __init__(self, entity_type: str, field: str, value: str):
        self.entity_type = entity_type
        self.field = field
        self.value = value
        super().__init__(f"{entity_type} with {field}='{value}' already exists")


class ChatProviderError(Exception):
    """Raised when a chat provider returns an error.

    Provider-agnostic — works for OpenRouter, Groq, OpenAI, etc.
    """

    def __init__(self, provider: str, status_code: int, message: str):
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{provider}] {status_code}: {message}")
