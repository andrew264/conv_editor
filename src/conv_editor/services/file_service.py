import json
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self, root: str):
        self._root_path = Path(root).resolve()
        self._working_dir: Optional[Path] = None
        self._ensure_root_exists()

    @property
    def root(self) -> Path:
        return self._root_path

    @property
    def working_dir_name(self) -> Optional[str]:
        return self._working_dir.name if self._working_dir else None

    def _ensure_root_exists(self):
        if not self._root_path.exists():
            logger.warning(f"Root directory does not exist. Creating: {self._root_path}")
            self._root_path.mkdir(parents=True, exist_ok=True)
        elif not self._root_path.is_dir():
            raise NotADirectoryError(f"Root path is not a directory: {self._root_path}")

    def set_root(self, new_root: str):
        self._root_path = Path(new_root).resolve()
        self._working_dir = None
        self._ensure_root_exists()
        logger.info(f"Root directory set to: {self._root_path}")

    def set_working_dir(self, directory_name: str):
        if not directory_name:
            self._working_dir = None
            logger.warning("Working directory cleared.")
            return

        path = self._root_path / directory_name
        if path.is_dir():
            self._working_dir = path
            logger.info(f"Working directory set to: {path}")
        else:
            raise FileNotFoundError(f"Directory not found in root: {directory_name}")

    def list_directories(self) -> List[str]:
        return sorted([d.name for d in self._root_path.iterdir() if d.is_dir()])

    def list_files_in_working_dir(self) -> List[str]:
        if not self._working_dir:
            return []
        return sorted([f.name for f in self._working_dir.iterdir() if f.is_file() and f.suffix == ".json"])

    def get_full_path(self, file_name: str) -> Optional[Path]:
        if not self._working_dir:
            return None
        return self._working_dir / file_name

    def create_new_file(self, file_name: str) -> Optional[Path]:
        if not self._working_dir:
            logger.error("Cannot create file: no working directory is set.")
            return None

        if not file_name.endswith(".json"):
            file_name += ".json"

        file_path = self._working_dir / file_name
        if file_path.exists():
            logger.warning(f"File already exists, cannot create: {file_path}")
            return None

        try:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)
            logger.info(f"Created new empty file: {file_path}")
            return file_path
        except OSError as e:
            logger.error(f"Failed to create file '{file_path}': {e}")
            return None
