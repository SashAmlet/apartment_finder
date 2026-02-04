import asyncio
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from typing import List, Dict, Any, Union
import joblib
from datetime import datetime

from .base import Classifier
from models import TelegramMessage


class RandomForestMessageClassifier(Classifier):
    def __init__(self, n_estimators: int = 100, random_state: int = 42):
        super().__init__()
        
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=random_state,
            class_weight="balanced"
        )

    async def train(self, messages: Union[List[TelegramMessage], np.ndarray], labels: List[int], to_vectorize: bool = True) -> None:
        """Асинхронное обучение модели"""
        if to_vectorize:
            X = await self._vectorize(messages)
        else:
            X = messages
        y = np.array(labels)
        await asyncio.to_thread(self.model.fit, X, y)

    async def predict(self, messages: Union[List[TelegramMessage], np.ndarray], to_vectorize: bool = True) -> List[int]:
        """Асинхронное предсказание"""
        if to_vectorize:
            X = await self._vectorize(messages)
        else:
            X = messages
        preds = await asyncio.to_thread(self.model.predict, X)
        return preds.tolist()

    async def predict_with_confidence(self, messages: Union[List[TelegramMessage], np.ndarray], to_vectorize: bool = True) -> List[Dict[str, Any]]:
        """Асинхронное предсказание с уверенностью"""
        if to_vectorize:
            X = await self._vectorize(messages)
        else:
            X = messages
        probs = await asyncio.to_thread(self.model.predict_proba, X)

        results = []
        for p in probs:
            predicted_class = int(np.argmax(p))
            confidence = float(np.max(p))
            results.append({
                "class": predicted_class,
                "confidence": confidence
            })
        return results

    async def save(self, path: str = None) -> None:
        """Асинхронное сохранение модели"""
        if path is None:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = f".\\models\\RF_model_{now}.joblib"

        await asyncio.to_thread(joblib.dump, self.model, path)

    async def load(self, path: str) -> None:
        """Асинхронная загрузка модели"""
        model = await asyncio.to_thread(joblib.load, path)
        if not hasattr(model, "estimators_"):
            raise RuntimeError("Загруженная модель не обучена или файл повреждён.")
        self.model = model
