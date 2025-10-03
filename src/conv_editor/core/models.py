from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, ValidationInfo


class TextSegment(BaseModel):
    text: str
    learnable: bool = True


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    segments: List[TextSegment]

    @field_validator("segments", mode="before")
    @classmethod
    def handle_legacy_text_field(cls, v: Any, info: ValidationInfo) -> Any:
        """Handles in-place migration for old files that have a 'text' field."""
        if "text" in info.data and isinstance(info.data["text"], str):
            return [TextSegment(text=info.data["text"])]
        if not v:
            return [TextSegment(text="")]
        return v

    @property
    def full_text(self) -> str:
        return "".join(s.text for s in self.segments)


class ReasoningContent(BaseModel):
    type: Literal["reason"] = "reason"
    segments: List[TextSegment]

    @field_validator("segments", mode="before")
    @classmethod
    def handle_legacy_text_field(cls, v: Any, info: ValidationInfo) -> Any:
        if "text" in info.data and isinstance(info.data["text"], str):
            return [TextSegment(text=info.data["text"])]
        if not v:
            return [TextSegment(text="")]
        return v

    @property
    def full_text(self) -> str:
        return "".join(s.text for s in self.segments)


class ToolProperty(BaseModel):
    type: Union[str, List[str]]
    description: str
    enum: Optional[List[str]] = None


class ToolParameters(BaseModel):
    type: Literal["object"] = "object"
    properties: Dict[str, ToolProperty]
    required: List[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str
    parameters: ToolParameters


class ToolsContent(BaseModel):
    type: Literal["tools"] = "tools"
    definitions: List[ToolDefinition]


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]


class ToolCallContent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    calls: List[ToolCall]


class ToolResult(BaseModel):
    name: str
    content: Any


class ToolResultsContent(BaseModel):
    type: Literal["tool_response"] = "tool_response"
    results: List[ToolResult]


# Core Conversation Structure
ContentItem = Annotated[
    Union[
        TextContent,
        ReasoningContent,
        ToolsContent,
        ToolCallContent,
        ToolResultsContent,
    ],
    Field(discriminator="type"),
]


class Item(BaseModel):
    role: str
    content: List[ContentItem]


ConversationData = List[Item]


# Search Model
class SearchMatch(BaseModel):
    file_path: str
    preview: str
    score: float
    match_indices: Optional[Tuple[int, int]] = None
    item_index: Optional[int] = None
