from pathlib import Path

from pydantic import BaseModel, Field


class SpecialTokensConfig(BaseModel):
    bos: str = Field("<|begin_of_text|>", description="Beginning of Sequence token.")
    eot: str = Field("<|eot_id|>", description="End of Turn token.")
    header_start: str = Field("<|start_header_id|>", description="Token starting a role header.")
    header_end: str = Field("<|end_header_id|>", description="Token ending a role header.")
    think_start: str = Field("<think>", description="Token starting a reasoning block.")
    think_end: str = Field("</think>", description="Token ending a reasoning block.")
    tools_start: str = Field("<tools>", description="Token starting a tool definition block.")
    tools_end: str = Field("</tools>", description="Token ending a tool definition block.")
    tool_call_start: str = Field("<tool_call>", description="Token starting a tool call block.")
    tool_call_end: str = Field("</tool_call>", description="Token ending a tool call block.")
    tool_response_start: str = Field("<tool_response>", description="Token starting a tool response block.")
    tool_response_end: str = Field("</tool_response>", description="Token ending a tool response block.")


class ExportConfig(BaseModel):
    root_directory: Path = Field(..., description="The root directory containing conversation files to process.")
    tokenizer_path: Path = Field(..., description="Path to the tokenizer.json file.")
    output_path: Path = Field(..., description="Path to the output HDF5 file.")
    include_reasoning: bool = Field(True, description="Whether to include reasoning/think blocks in the output.")
    special_tokens: SpecialTokensConfig = Field(default_factory=SpecialTokensConfig, description="Configuration for all special tokens.")
    cross_entropy_ignore_index: int = Field(-100, description="Index to use for non-learnable tokens in the labels.")
    assistant_name: str = Field("assistant", description="The role name used for the assistant.")
