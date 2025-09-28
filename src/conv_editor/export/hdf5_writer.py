import logging
from pathlib import Path
from typing import Dict

import h5py
import numpy as np

logger = logging.getLogger(__name__)


class HDF5Writer:
    def __init__(self, filepath: Path, chunk_size: int = 2048):
        self.filepath = filepath
        self.chunk_size = chunk_size
        self.file = None
        self.size = 0

    def __enter__(self):
        try:
            self.file = h5py.File(self.filepath, "w")
            self.file.create_dataset(
                "input_ids",
                shape=(0,),
                maxshape=(None,),
                dtype=np.int32,
                chunks=(self.chunk_size,),
            )
            self.file.create_dataset(
                "labels",
                shape=(0,),
                maxshape=(None,),
                dtype=np.int32,
                chunks=(self.chunk_size,),
            )
            logger.info(f"Opened HDF5 file for writing at {self.filepath}")
            return self
        except Exception as e:
            logger.error(f"Failed to create or open HDF5 file {self.filepath}: {e}")
            raise

    def append(self, data: Dict[str, np.ndarray]):
        if not self.file:
            raise IOError("HDF5 file is not open. Use within a 'with' statement.")

        input_ids = data.get("input_ids")
        labels = data.get("labels")

        if input_ids is None or labels is None:
            raise ValueError("Data dictionary must contain 'input_ids' and 'labels'.")
        if len(input_ids) != len(labels):
            raise ValueError(f"Length of input_ids ({len(input_ids)}) and labels ({len(labels)}) must be equal.")

        num_new_tokens = len(input_ids)
        if num_new_tokens == 0:
            return

        new_size = self.size + num_new_tokens

        self.file["input_ids"].resize((new_size,))
        self.file["labels"].resize((new_size,))

        self.file["input_ids"][self.size :] = input_ids
        self.file["labels"][self.size :] = labels

        self.size = new_size

    def close(self):
        if self.file:
            logger.info(f"Closing HDF5 file. Total tokens written: {self.size}")
            self.file.close()
            self.file = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
