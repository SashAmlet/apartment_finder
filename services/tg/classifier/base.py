from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np
import asyncio

from models import TelegramMessage
from .message_processor import FeatureExtractor

class Classifier(ABC):
    def __init__(self):
        self.extractor = FeatureExtractor()

    async def _vectorize(self, messages: List[TelegramMessage]) -> np.ndarray:
        """Асинхронная векторизация сообщений"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            lambda: np.array([list(self.extractor.extract(msg).values()) for msg in messages])
        )

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