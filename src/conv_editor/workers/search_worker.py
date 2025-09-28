import logging

from PySide6.QtCore import QThread, Signal

from conv_editor.core.models import SearchMatch
from conv_editor.services.search_service import SearchService

logger = logging.getLogger(__name__)


class SearchWorker(QThread):
    result_found = Signal(SearchMatch)
    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        root_dir: str,
        query: str,
        is_fuzzy: bool,
        score_cutoff: int,
        case_insensitive: bool,
        max_results: int,
        parent=None,
    ):
        super().__init__(parent)
        self.root_dir = root_dir
        self.query = query
        self.is_fuzzy = is_fuzzy
        self.score_cutoff = score_cutoff
        self.case_insensitive = case_insensitive
        self.max_results = max_results
        self._is_running = True

    def run(self):
        try:
            search_service = SearchService()
            results_found = 0
            search_iterator = (
                search_service.fuzzy_search(self.root_dir, self.query, self.score_cutoff)
                if self.is_fuzzy
                else search_service.exact_search(self.root_dir, self.query, self.case_insensitive)
            )

            for result in search_iterator:
                if not self._is_running or results_found >= self.max_results:
                    break
                self.result_found.emit(result)
                results_found += 1
        except Exception as e:
            logger.exception("Error during search execution in worker.")
            self.error.emit(str(e))
        finally:
            logger.info("SearchWorker finished.")
            self.finished.emit()

    def stop(self):
        logger.info("Stopping SearchWorker...")
        self._is_running = False
