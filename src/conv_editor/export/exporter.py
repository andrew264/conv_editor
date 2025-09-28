import json
import logging
from typing import Dict, List

import numpy as np
from tokenizers import Tokenizer

from conv_editor.core.models import (
    ConversationData,
    Item,
    ReasoningContent,
    TextContent,
    ToolCallContent,
    ToolResultsContent,
    ToolsContent,
)
from conv_editor.export.config import ExportConfig

logger = logging.getLogger(__name__)


class TrainingExporter:
    def __init__(self, tokenizer: Tokenizer, config: ExportConfig):
        self.tokenizer = tokenizer
        self.config = config
        self.tokens = config.special_tokens

    def _serialize_tools(self, content: ToolsContent) -> str:
        try:
            definitions_as_dicts = [d.model_dump(exclude_none=True) for d in content.definitions]
            json_str = json.dumps(definitions_as_dicts, separators=(",", ":"))
            return f"{self.tokens.tools_start}{json_str}{self.tokens.tools_end}"
        except Exception:
            return f"{self.tokens.tools_start}[]{self.tokens.tools_end}"

    def _serialize_tool_calls(self, content: ToolCallContent) -> str:
        try:
            calls_as_dicts = [c.model_dump(exclude_none=True) for c in content.calls]
            call_strings = []
            for call_dict in calls_as_dicts:
                json_str = json.dumps(call_dict, separators=(",", ":"))
                call_strings.append(f"{self.tokens.tool_call_start}{json_str}{self.tokens.tool_call_end}")
            return "\n".join(call_strings)
        except Exception:
            return f"{self.tokens.tool_call_start}{{}}{self.tokens.tool_call_end}"

    def _serialize_tool_results(self, content: ToolResultsContent) -> str:
        try:
            results_as_dicts = [r.model_dump(exclude_none=True) for r in content.results]
            json_str = json.dumps(results_as_dicts, separators=(",", ":"))
            return f"{self.tokens.tool_response_start}{json_str}{self.tokens.tool_response_end}"
        except Exception:
            return f"{self.tokens.tool_response_start}[]{self.tokens.tool_response_end}"

    def process_conversation(self, conversation_data: ConversationData) -> Dict[str, np.ndarray]:
        all_input_ids: List[int] = []
        all_labels: List[int] = []

        bos_encoding = self.tokenizer.encode(self.tokens.bos, add_special_tokens=False)
        all_input_ids.extend(bos_encoding.ids)
        all_labels.extend([self.config.cross_entropy_ignore_index] * len(bos_encoding.ids))

        for item in conversation_data:
            self._process_item(item, all_input_ids, all_labels)

        return {
            "input_ids": np.array(all_input_ids, dtype=np.int32),
            "labels": np.array(all_labels, dtype=np.int32),
        }

    def _process_item(self, item: Item, all_input_ids: List[int], all_labels: List[int]):
        ignore = self.config.cross_entropy_ignore_index
        is_assistant_turn = item.role == self.config.assistant_name

        header_str = f"{self.tokens.header_start}{item.role}{self.tokens.header_end}\n"
        header_encoding = self.tokenizer.encode(header_str, add_special_tokens=False)
        all_input_ids.extend(header_encoding.ids)
        all_labels.extend([ignore] * len(header_encoding.ids))

        for content_part in item.content:
            if isinstance(content_part, TextContent):
                for segment in content_part.segments:
                    segment_encoding = self.tokenizer.encode(segment.text, add_special_tokens=False)
                    all_input_ids.extend(segment_encoding.ids)
                    if segment.learnable and is_assistant_turn:
                        all_labels.extend(segment_encoding.ids)
                    else:
                        all_labels.extend([ignore] * len(segment_encoding.ids))

            elif isinstance(content_part, ReasoningContent):
                if self.config.include_reasoning:
                    think_start_encoding = self.tokenizer.encode(self.tokens.think_start, add_special_tokens=False)
                    all_input_ids.extend(think_start_encoding.ids)
                    all_labels.extend(think_start_encoding.ids)

                    for segment in content_part.segments:
                        segment_encoding = self.tokenizer.encode(segment.text, add_special_tokens=False)
                        all_input_ids.extend(segment_encoding.ids)
                        if segment.learnable:
                            all_labels.extend(segment_encoding.ids)
                        else:
                            all_labels.extend([ignore] * len(segment_encoding.ids))

                    think_end_encoding = self.tokenizer.encode(self.tokens.think_end + "\n", add_special_tokens=False)
                    all_input_ids.extend(think_end_encoding.ids)
                    all_labels.extend(think_end_encoding.ids)

            elif isinstance(content_part, ToolCallContent):
                tcall_str = self._serialize_tool_calls(content_part) + "\n"
                tcall_encoding = self.tokenizer.encode(tcall_str, add_special_tokens=False)
                all_input_ids.extend(tcall_encoding.ids)
                all_labels.extend(tcall_encoding.ids)

            elif isinstance(content_part, ToolsContent):
                tools_str = self._serialize_tools(content_part) + "\n"
                tools_encoding = self.tokenizer.encode(tools_str, add_special_tokens=False)
                all_input_ids.extend(tools_encoding.ids)
                all_labels.extend([ignore] * len(tools_encoding.ids))

            elif isinstance(content_part, ToolResultsContent):
                tresults_str = self._serialize_tool_results(content_part) + "\n"
                tresults_encoding = self.tokenizer.encode(tresults_str, add_special_tokens=False)
                all_input_ids.extend(tresults_encoding.ids)
                all_labels.extend([ignore] * len(tresults_encoding.ids))

        eot_encoding = self.tokenizer.encode(self.tokens.eot, add_special_tokens=False)
        all_input_ids.extend(eot_encoding.ids)
        if is_assistant_turn:
            all_labels.extend(eot_encoding.ids)  # assistant should know when to stop yapping
        else:
            all_labels.extend([ignore] * len(eot_encoding.ids))
