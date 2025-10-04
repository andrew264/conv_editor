import logging
import threading
from typing import Dict, Iterator, List

from openai import OpenAI, OpenAIError

from conv_editor.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.model = settings.OPENAI_MODEL_NAME
        self._lock = threading.Lock()
        self._is_running = False

        try:
            self.client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
            logger.info(f"OpenAI client initialized for model '{self.model}'.")
            if settings.OPENAI_BASE_URL:
                logger.info(f"Using custom base URL: {settings.OPENAI_BASE_URL}")
        except Exception as e:
            logger.critical(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            raise

    @property
    def is_generating(self) -> bool:
        return self._is_running

    def stop_generation(self):
        if self._is_running:
            logger.info("Requesting to stop OpenAI generation.")
            self._is_running = False

    def get_chat_response_stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        with self._lock:
            if self._is_running:
                logger.warning("Chat generation is already in progress.")
                return
            self._is_running = True

        try:
            stream = self.client.chat.completions.create(model=self.model, messages=messages, stream=True)
            for chunk in stream:
                if not self._is_running:
                    logger.info("Chat stream stopped by user.")
                    break
                if chunk.choices:
                    if hasattr(chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content is not None:
                        yield chunk.choices[0].delta.reasoning_content
                    elif chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
        except OpenAIError as e:
            logger.error(f"OpenAI API error during chat stream: {e}")
            raise
        finally:
            self._is_running = False
            logger.info("Chat generation stream finished.")

    def get_completion_response_stream(self, prompt: str) -> Iterator[str]:
        with self._lock:
            if self._is_running:
                logger.warning("Chat generation is already in progress.")
                return
            self._is_running = True

        try:
            stream = self.client.completions.create(model=self.model, prompt=prompt, stream=True)
            for chunk in stream:
                if not self._is_running:
                    logger.info("Completion stream stopped by user.")
                    break
                if not chunk.choices and hasattr(chunk, "content"):
                    yield chunk.content
                elif chunk.choices and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except OpenAIError as e:
            logger.error(f"OpenAI API error during Completion stream: {e}")
            raise
        finally:
            self._is_running = False
            logger.info("Completion generation stream finished.")
