import json
from typing import Dict, Optional

from conv_editor.core.models import (
    ConversationData,
    ReasoningContent,
    TextContent,
    ToolCallContent,
    ToolResultsContent,
    ToolsContent,
)


class PromptFormatter:
    DEFAULT_TOKENS = {
        "bos": "<|begin_of_text|>",
        "eot": "<|eot_id|>",
        "header_start": "<|start_header_id|>",
        "header_end": "<|end_header_id|>",
        "think_start": "<think>",
        "think_end": "</think>",
        "tools_start": "<tools>",
        "tools_end": "</tools>",
        "tool_call_start": "<tool_call>",
        "tool_call_end": "</tool_call>",
        "tool_response_start": "<tool_response>",
        "tool_response_end": "</tool_response>",
    }

    def __init__(self, special_tokens: Optional[Dict[str, str]] = None, json_indent: Optional[int] = 0):
        self.tokens = self.DEFAULT_TOKENS.copy()
        if special_tokens:
            self.tokens.update(special_tokens)
        self.json_indent = json_indent

    def _serialize_tools(self, content: ToolsContent) -> str:
        try:
            definitions_as_dicts = [d.model_dump(exclude_none=True) for d in content.definitions]
            json_str = json.dumps(definitions_as_dicts, indent=self.json_indent)
            return f"{self.tokens['tools_start']}\n{json_str}\n{self.tokens['tools_end']}"
        except Exception:
            return f"{self.tokens['tools_start']}\n[]\n{self.tokens['tools_end']}"

    def _serialize_tool_calls(self, content: ToolCallContent) -> str:
        try:
            calls_as_dicts = [c.model_dump(exclude_none=True) for c in content.calls]
            call_strings = []
            for call_dict in calls_as_dicts:
                json_str = json.dumps(call_dict, indent=self.json_indent)
                call_strings.append(f"{self.tokens['tool_call_start']}\n{json_str}\n{self.tokens['tool_call_end']}")
            return "\n".join(call_strings)
        except Exception:
            return f"{self.tokens['tool_call_start']}\n{{}}\n{self.tokens['tool_call_end']}"

    def _serialize_tool_results(self, content: ToolResultsContent) -> str:
        try:
            results_as_dicts = [r.model_dump(exclude_none=True) for r in content.results]
            json_str = json.dumps(results_as_dicts, indent=self.json_indent)
            return f"{self.tokens['tool_response_start']}\n{json_str}\n{self.tokens['tool_response_end']}"
        except Exception:
            return f"{self.tokens['tool_response_start']}\n[]\n{self.tokens['tool_response_end']}"

    def __call__(
        self,
        data_slice: ConversationData,
        assistant_name: str,
        with_reason: bool,
    ) -> str:
        parts = [self.tokens["bos"]]

        for item in data_slice:
            header = f"{self.tokens['header_start']}{item.role}{self.tokens['header_end']}\n\n"
            turn_content_parts = []

            for content_part in item.content:
                if isinstance(content_part, TextContent):
                    turn_content_parts.append(content_part.full_text)
                elif isinstance(content_part, ReasoningContent):
                    if with_reason:
                        think_block = f"{self.tokens['think_start']}{content_part.full_text}{self.tokens['think_end']}"
                        turn_content_parts.append(think_block)
                elif isinstance(content_part, ToolsContent):
                    turn_content_parts.append(self._serialize_tools(content_part))
                elif isinstance(content_part, ToolCallContent):
                    turn_content_parts.append(self._serialize_tool_calls(content_part))
                elif isinstance(content_part, ToolResultsContent):
                    turn_content_parts.append(self._serialize_tool_results(content_part))

            full_turn_content = "".join(turn_content_parts)
            turn_string = f"{header}{full_turn_content}\n{self.tokens['eot']}"
            parts.append(turn_string)

        # generation prompt for the assistant
        assistant_prompt = f"\n{self.tokens['header_start']}{assistant_name}{self.tokens['header_end']}\n\n"
        parts.append(assistant_prompt)

        return "".join(parts)
