from dataclasses import dataclass, field
from typing import Any, Literal


MessageRole = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class ChatMessage:
    """One message in a provider-neutral conversation."""

    role: MessageRole
    content: str
    images: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass(frozen=True)
class ToolExecutionResult:
    name: str
    success: bool
    output: Any
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)
    id: str | None = None


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    required_capabilities: set[str] = field(default_factory=set)
    required_modality: str = "text"
    images: list[str] = field(default_factory=list)
    # Provider-neutral document attachments.  Providers may accept encoded
    # documents directly or transform them into their native attachment form.
    documents: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolExecutionResult] = field(default_factory=list)
    messages: list[ChatMessage] = field(default_factory=list)


@dataclass(frozen=True)
class ModelResponse:
    content: str
    model_id: str
    raw: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)


MAX_HISTORY_MESSAGES = 50
MAX_HISTORY_CONTENT_CHARS = 100_000


def validate_chat_messages(messages: list["ChatMessage"]) -> None:
    """Validate the provider-neutral chat message contract."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    for index, message in enumerate(messages):
        if not isinstance(message, ChatMessage):
            raise ValueError(f"messages[{index}] must be a ChatMessage")
        if message.role not in {"user", "assistant", "system"}:
            raise ValueError(f"messages[{index}].role must be user, assistant, or system")
        if not isinstance(message.content, str):
            raise ValueError(f"messages[{index}].content must be a string")
        if message.role in {"user", "system"} and not message.content.strip():
            raise ValueError(f"messages[{index}].content must not be empty")
        if not isinstance(message.images, list) or any(
            not isinstance(image, str) or not image.strip() for image in message.images
        ):
            raise ValueError(f"messages[{index}].images must be a list of non-empty strings")


def normalize_messages(
    messages: list["ChatMessage"] | None,
    prompt: str,
    images: list[str] | None = None,
) -> list["ChatMessage"]:
    """Use supplied history or synthesize messages from prompt."""
    if messages:
        validate_chat_messages(messages)
        normalized = list(messages)
        has_system = any(m.role == "system" for m in normalized)
        if not has_system and isinstance(prompt, str) and prompt.startswith("System instructions:\n"):
            parts = prompt.split("\n\nUser request:\n", 1)
            sys_text = parts[0].replace("System instructions:\n", "", 1).strip()
            if sys_text:
                normalized.insert(0, ChatMessage(role="system", content=sys_text))
    else:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be non-empty when messages is empty")
        if prompt.startswith("System instructions:\n") and "\n\nUser request:\n" in prompt:
            parts = prompt.split("\n\nUser request:\n", 1)
            sys_text = parts[0].replace("System instructions:\n", "", 1).strip()
            user_text = parts[1].strip()
            normalized = [
                ChatMessage(role="system", content=sys_text),
                ChatMessage(role="user", content=user_text),
            ]
        else:
            normalized = [ChatMessage(role="user", content=prompt)]
    if images:
        latest_user_index = max(
            (index for index, message in enumerate(normalized) if message.role == "user"),
            default=-1,
        )
        if latest_user_index >= 0:
            latest = normalized[latest_user_index]
            normalized[latest_user_index] = ChatMessage(
                role="user",
                content=latest.content,
                images=[*latest.images, *images],
            )
        else:
            normalized.append(ChatMessage(role="user", content="", images=list(images)))
    return normalized


def trim_messages(
    messages: list["ChatMessage"],
    *,
    max_messages: int = MAX_HISTORY_MESSAGES,
    max_content_chars: int = MAX_HISTORY_CONTENT_CHARS,
) -> list["ChatMessage"]:
    """Retain the newest bounded conversation while preserving the latest user turn."""
    validate_chat_messages(messages)
    if not messages:
        return []

    latest_user_index = max(
        index for index, message in enumerate(messages) if message.role == "user"
    )
    retained_indices = {latest_user_index}
    retained_indices.update(
        index for index, message in enumerate(messages) if message.role == "system"
    )
    content_chars = sum(len(messages[index].content) for index in retained_indices)

    for index in range(len(messages) - 1, -1, -1):
        if index in retained_indices:
            continue
        message = messages[index]
        if len(retained_indices) >= max_messages:
            break
        if content_chars + len(message.content) > max_content_chars:
            continue
        retained_indices.add(index)
        content_chars += len(message.content)
        if len(retained_indices) >= max_messages:
            break

    return [messages[index] for index in sorted(retained_indices)]


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    runtime: str
    model: str
    capabilities: set[str]
    modalities: set[str]
    priority: int = 0
    enabled: bool = True
