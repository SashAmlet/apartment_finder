from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np
import asyncio
import ollama
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


    def _ollama_embed_impl(self, texts: list[str], model: str) -> np.ndarray:
        """Helper: call ollama.embed and normalize response to numpy array."""
        if ollama is None:
            raise RuntimeError("ollama client is not installed or failed to import")

        resp = ollama.embed(model=model, input=texts)
        if hasattr(resp, "embeddings"):
            return np.array(resp.embeddings)
        if isinstance(resp, list):
            if resp and hasattr(resp[0], "embeddings"):
                return np.array([r.embeddings for r in resp])
            return np.array(resp)
        if isinstance(resp, dict) and "embeddings" in resp:
            return np.array(resp["embeddings"])
        raise RuntimeError("Unexpected response format from ollama.embed")
    
    def _gpu_vectorize_sync(self, texts: list[str]) -> np.ndarray:
        """Синхронная часть, которая выполняется на GPU"""
        print("⏳ Загрузка модели в видеопамять...")
        
        # Проверка доступности GPU
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🚀 Используем устройство: {device.upper()}")
        if device == 'cpu':
            print("⚠️ ВНИМАНИЕ: GPU не обнаружен! Будет медленно.")

        # Загружаем модель (она сама скачается при первом запуске)
        model = SentenceTransformer('BAAI/bge-m3', device=device)
        
        print(f"🔄 Начало векторизации {len(texts)} сообщений...")
        
        # batch_size=32 или 64 идеально для RTX 3050 (4GB VRAM)
        embeddings = model.encode(
            texts, 
            batch_size=32, 
            show_progress_bar=True, 
            convert_to_numpy=True,
            normalize_embeddings=True # Важно для bge-m3
        )
        return embeddings

    async def _vectorize(self, messages: List[TelegramMessage], method: str = "gpu", **kwargs) -> np.ndarray:
        """Asynchronous vectorization of messages.

        Parameters
        ----------
        messages : list[TelegramMessage]
            Messages to vectorize.
        method : str
            One of:
              - "features" (default) : use local FeatureExtractor -> numeric features
              - "ollama" : use Ollama embeddings; accepts `model` kwarg
        kwargs : dict
            Additional backend-specific options. For `ollama`, pass `model`.
        """
        loop = asyncio.get_running_loop()

        if method == "features":
            return await loop.run_in_executor(None, self._features_vectorize_impl, messages, self.extractor)

        if method == "ollama":
            model = kwargs.get("model", "bge-m3")
            texts = [m.text if hasattr(m, "text") else str(m) for m in messages]
            # run embedding in thread
            return await asyncio.to_thread(self._ollama_embed_impl, texts, model)
        
        if method == "gpu":
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
        """Сохраняет модель на диск"""
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Загружает модель с диска"""
        pass