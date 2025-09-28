import json
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from rapidfuzz import fuzz, utils

from conv_editor.core.models import SearchMatch

logger = logging.getLogger(__name__)


class SearchService:
    def fuzzy_search(self, root_dir: str, query: str, score_cutoff: int) -> Iterator[SearchMatch]:
        root_path = Path(root_dir)
        if not query or not root_path.is_dir():
            return

        logger.info(f"Starting fuzzy search for '{query}' in {root_path}")
        for json_path in root_path.rglob("*.json"):
            try:
                file_content = json_path.read_text(encoding="utf-8")
                lines = file_content.splitlines()
                conversation_data = None  # Lazy load

                for line_idx, line in enumerate(lines):
                    score = fuzz.partial_ratio(query, line, processor=utils.default_process)
                    if score >= score_cutoff:
                        indices = self._find_best_match_indices(line, query)
                        if conversation_data is None:
                            conversation_data = self._load_conversation_safe(file_content)

                        item_idx = self._find_item_index_fuzzy(conversation_data, line, indices)
                        yield SearchMatch(
                            file_path=str(json_path.resolve()),
                            preview=line,
                            match_indices=indices,
                            item_index=item_idx,
                            score=score,
                        )
            except Exception as e:
                logger.warning(f"Could not process file '{json_path}' for search: {e}")

    def exact_search(self, root_dir: str, query: str, case_insensitive: bool) -> Iterator[SearchMatch]:
        root_path = Path(root_dir)
        if not query or not root_path.is_dir():
            return

        logger.info(f"Starting exact search for '{query}' in {root_path}")
        search_query = query.lower() if case_insensitive else query

        for json_path in root_path.rglob("*.json"):
            try:
                file_content = json_path.read_text(encoding="utf-8")
                lines = file_content.splitlines()
                conversation_data = None  # Lazy load

                for line_idx, line in enumerate(lines):
                    search_line = line.lower() if case_insensitive else line
                    if search_query in search_line:
                        indices = self._find_exact_indices(line, query, case_insensitive)
                        if conversation_data is None:
                            conversation_data = self._load_conversation_safe(file_content)

                        item_idx = self._find_item_index_exact(conversation_data, line, indices, case_insensitive)
                        yield SearchMatch(
                            file_path=str(json_path.resolve()),
                            preview=line,
                            match_indices=indices,
                            item_index=item_idx,
                            score=100,
                        )
            except Exception as e:
                logger.warning(f"Could not process file '{json_path}' for search: {e}")

    @staticmethod
    def _load_conversation_safe(content: str) -> Optional[List[Dict]]:
        try:
            data = json.loads(content)
            return data if isinstance(data, list) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _find_best_match_indices(line: str, query: str, min_ratio: int = 60) -> Optional[Tuple[int, int]]:
        q_len, l_len = len(query), len(line)
        if not q_len or not l_len:
            return None

        best_score, best_indices = -1, None
        for i in range(max(0, l_len - q_len + 1)):
            substring = line[i : i + q_len]
            score = fuzz.ratio(query, substring, processor=utils.default_process)
            if score > best_score:
                best_score, best_indices = score, (i, i + q_len)

        return best_indices if best_score >= min_ratio and best_indices else None

    @staticmethod
    def _find_exact_indices(line: str, query: str, case_insensitive: bool) -> Optional[Tuple[int, int]]:
        search_line = line.lower() if case_insensitive else line
        search_query = query.lower() if case_insensitive else query
        start_idx = search_line.find(search_query)
        return (start_idx, start_idx + len(query)) if start_idx != -1 else None

    @staticmethod
    def _find_item_index_fuzzy(conversation: Optional[List[Dict]], line: str, indices: Optional[Tuple[int, int]]) -> Optional[int]:
        if not conversation or not indices:
            return None

        matched_text = line[indices[0] : indices[1]]
        if not matched_text:
            return None

        for idx, item in enumerate(conversation):
            if "content" in item and isinstance(item["content"], list):
                for content_part in item["content"]:
                    if "text" in content_part and isinstance(content_part["text"], str):
                        score = fuzz.partial_ratio(
                            matched_text,
                            content_part["text"],
                            processor=utils.default_process,
                        )
                        if score > 95:
                            return idx
        return None

    @staticmethod
    def _find_item_index_exact(
        conversation: Optional[List[Dict]],
        line: str,
        indices: Optional[Tuple[int, int]],
        case_insensitive: bool,
    ) -> Optional[int]:
        if not conversation or not indices:
            return None

        matched_text = line[indices[0] : indices[1]]
        if not matched_text:
            return None

        search_matched_text = matched_text.lower() if case_insensitive else matched_text

        for idx, item in enumerate(conversation):
            if "content" in item and isinstance(item["content"], list):
                for content_part in item["content"]:
                    if "text" in content_part and isinstance(content_part["text"], str):
                        search_text = content_part["text"].lower() if case_insensitive else content_part["text"]
                        if search_matched_text in search_text:
                            return idx
        return None
