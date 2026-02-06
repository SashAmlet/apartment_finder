from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np
import asyncio
import torch
from sentence_transformers import SentenceTransformer

from models import TelegramMessage
from .message_processor import FeatureExtractor

class Classifier(ABC):
    def __init__(self):
        self.extractor = FeatureExtractor()

    def _features_vectorize_impl(self, messages, extractor: FeatureExtractor) -> np.ndarray:
        """Helper: extract numeric features for a list of messages using extractor."""
        return np.array([list(extractor.extract(msg).values()) for msg in messages])
    
    def _gpu_vectorize_sync(self, texts: list[str]) -> np.ndarray:
        """Synchronous GPU/CPU encoding using a SentenceTransformer model.

        This method runs on the calling thread (it is intended to be executed
        inside a thread-pool executor). It loads a BGE model and returns a
        matrix of normalized embeddings.
        """

        print("Loading model to device memory...")

        # choose device
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device.upper()}")
        if device == 'cpu':
            print("Warning: GPU not detected — encoding will be slower on CPU.")

        # Load the model (will be downloaded on first use)
        model = SentenceTransformer('BAAI/bge-m3', device=device)

        print(f"Starting encoding of {len(texts)} messages...")

        # Typical batch_size values: 32 or 64 depending on GPU memory
        embeddings = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings

    async def _vectorize(self, messages: List[TelegramMessage], method: str = "bge-m3", **kwargs) -> np.ndarray:
        """Asynchronous vectorization of messages.

        Parameters
        ----------
        messages : list[TelegramMessage]
            Messages to vectorize.
        method : str
            Vectorization backend to use. Supported values:
              - "features": use local FeatureExtractor -> numeric features
              - "bge-m3": use a local SentenceTransformer BGE model (default)
              - "ollama": use Ollama embeddings (if configured)
        kwargs : dict
            Additional backend-specific options. For `ollama`, pass `model`.
        """
        loop = asyncio.get_running_loop()

        if method == "features":
            return await loop.run_in_executor(None, self._features_vectorize_impl, messages, self.extractor)
        
        if method == "bge-m3":
            texts = [m.text if hasattr(m, "text") else str(m) for m in messages]
            return await loop.run_in_executor(None, self._gpu_vectorize_sync, texts)

        raise ValueError(f"Unknown vectorization method: {method}")

    @abstractmethod
    def train(self, messages: List[TelegramMessage], labels: List[int]) -> None:
        pass

    @abstractmethod
    def predict(self, messages: List[TelegramMessage]) -> List[int]:
        pass

    @abstractmethod
    def predict_with_confidence(self, messages: List[TelegramMessage]) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def save(self, path: str = None) -> None:
        """Save the model to disk (synchronously/abstract API).

        Implementations should persist the trained model to `path` or a
        reasonable default location.
        """
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Load the model from disk (synchronously/abstract API)."""
        pass