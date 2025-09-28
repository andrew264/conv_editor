from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="CONV_EDITOR_", extra="ignore")

    # OpenAI Settings
    OPENAI_API_KEY: str = Field(..., validation_alias="OPENAI_API_KEY")
    OPENAI_MODEL_NAME: str = Field("gpt-4o", validation_alias="OPENAI_MODEL_NAME")
    OPENAI_BASE_URL: Optional[str] = Field(None, validation_alias="OPENAI_BASE_URL")

    # Application Settings
    APP_NAME: str = "ConversationEditor"
    APP_ORGANIZATION_NAME: str = "andrew264"
    APP_ROOT_DIR: str = ""
    APP_ASSISTANT_NAME: str = "assistant"
    APP_USE_REASONING: bool = False
    APP_SEARCH_SCORE_CUTOFF: int = Field(75, ge=0, le=100)

    # Theme Settings
    APP_THEME_UNLEARNABLE_BG: str = "#5A3A3A"  # Dark, desaturated red
    APP_THEME_UNLEARNABLE_FG: str = "#FFD6D6"  # Light pink/red text
    APP_THEME_REASONING_BG: str = "#2E2E2E"  # Slightly lighter than pure black
    APP_THEME_TOOLS_BG: str = "#2A3B4D"  # Dark slate blue
    APP_THEME_TOOL_RESULTS_BG: str = "#2A4D3B"  # Dark, desaturated green


settings = Settings()
