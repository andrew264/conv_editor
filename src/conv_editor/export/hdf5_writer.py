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
            vlen_dtype = h5py.special_dtype(vlen=np.int32)

            self.file.create_dataset(
                "input_ids",
                shape=(0,),
                maxshape=(None,),
                dtype=vlen_dtype,
                chunks=(1,),
            )
            self.file.create_dataset(
                "labels",
                shape=(0,),
                maxshape=(None,),
                dtype=vlen_dtype,
                chunks=(1,),
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
        if input_ids.ndim != 1:
            raise ValueError("input_ids for a single conversation must be a 1D array.")

        if len(input_ids) == 0:
            return

        new_size = self.size + 1
        self.file["input_ids"].resize((new_size,))
        self.file["labels"].resize((new_size,))

        self.file["input_ids"][self.size] = input_ids
        self.file["labels"][self.size] = labels

        self.size = new_size

    def close(self):
        if self.file:
            logger.info(f"Closing HDF5 file. Total conversations (rows) written: {self.size}")
            self.file.close()
            self.file = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
