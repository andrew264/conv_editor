import logging
from pathlib import Path
from typing import List, Optional, Tuple

import h5py
from tokenizers import Tokenizer

logger = logging.getLogger(__name__)


class H5ReaderService:
    def __init__(self, h5_path: Path, tokenizer_path: Path):
        self.h5_path = h5_path
        self.tokenizer_path = tokenizer_path
        self.tokenizer: Optional[Tokenizer] = None
        self.h5_file: Optional[h5py.File] = None
        self._conversation_count = 0

    def __enter__(self):
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def load(self):
        if not self.h5_path.exists():
            raise FileNotFoundError(f"HDF5 file not found: {self.h5_path}")
        if not self.tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer file not found: {self.tokenizer_path}")

        try:
            self.tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
            logger.info(f"Successfully loaded tokenizer from {self.tokenizer_path}")
        except Exception as e:
            logger.error(f"Failed to load tokenizer: {e}")
            raise ValueError(f"Could not load tokenizer file: {e}") from e

        try:
            self.h5_file = h5py.File(self.h5_path, "r")
            logger.info(f"Successfully opened HDF5 file: {self.h5_path}")
        except Exception as e:
            logger.error(f"Failed to open HDF5 file: {e}")
            raise ValueError(f"Could not open HDF5 file: {e}") from e

        self._validate_h5_structure()

    def _validate_h5_structure(self):
        if self.h5_file is None:
            raise IOError("HDF5 file is not open.")

        required_datasets = ["input_ids", "labels"]
        for ds_name in required_datasets:
            if ds_name not in self.h5_file:
                raise ValueError(f"HDF5 file is missing required dataset: '{ds_name}'")

        if len(self.h5_file["input_ids"]) != len(self.h5_file["labels"]):
            raise ValueError("Datasets 'input_ids' and 'labels' have mismatched lengths.")

        self._conversation_count = len(self.h5_file["input_ids"])
        logger.info(f"HDF5 file validation successful. Found {self._conversation_count} conversations.")

    @property
    def conversation_count(self) -> int:
        return self._conversation_count

    def get_processed_conversation(self, index: int) -> List[Tuple[str, bool]]:
        if not (0 <= index < self._conversation_count):
            raise IndexError("Conversation index out of range.")
        if self.h5_file is None or self.tokenizer is None:
            raise IOError("Service is not loaded. Use within a 'with' statement.")

        input_ids = self.h5_file["input_ids"][index]
        labels = self.h5_file["labels"][index]

        if len(input_ids) == 0:
            return []

        processed_segments = []
        start_idx = 0
        current_is_learnable = labels[0] != -100

        for i in range(1, len(labels)):
            is_learnable = labels[i] != -100
            if is_learnable != current_is_learnable:
                token_ids_segment = input_ids[start_idx:i]
                text = self.tokenizer.decode(token_ids_segment.tolist(), skip_special_tokens=False)
                processed_segments.append((text, current_is_learnable))

                start_idx = i
                current_is_learnable = is_learnable

        final_token_ids_segment = input_ids[start_idx:]
        final_text = self.tokenizer.decode(final_token_ids_segment.tolist(), skip_special_tokens=False)
        processed_segments.append((final_text, current_is_learnable))

        return processed_segments

    def close(self):
        if self.h5_file:
            self.h5_file.close()
            logger.info(f"Closed HDF5 file: {self.h5_path}")
            self.h5_file = None
