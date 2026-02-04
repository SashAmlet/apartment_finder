import os
import sys
import asyncio
import json
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from imblearn.pipeline import Pipeline
from collections import Counter

from models import TelegramMessage
from utils import load_channels
from services.tg.filter_service import TgFilterService
from services.tg.classifier.random_forest import RandomForestMessageClassifier


load_dotenv()


class BalancingStrategy(Enum):
    NONE = "none"
    HYBRID = "hybrid"
    SIMPLE_UNDER = "simple_under"

class ClassifyTester:
    def __init__(self, service: TgFilterService = None, output_file: str = None):
        self.service = service
        if output_file is None:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.output_file = f"data\\logs\\MessageClassifierService_test_results_{now}.json"
        else:
            self.output_file = output_file

    async def generate_test_messages(self, n: int = 100) -> List[TelegramMessage]:
        """Generate random test messages. In practice you can load a dataset here."""
        channels = await load_channels("data\\TelegramService\\2025-09-30_00-27-42.json")

        messages: List[TelegramMessage] = []
        for channel in channels:
            messages.extend(channel.messages[:n])
            n -= len(channel.messages)
            if n <= 0:
                break

        return messages

    async def get_test_sample(self, n: int = 100) -> List[TelegramMessage]:
        """Call AI analyzer on generated messages and save labeled results to JSON."""
        messages = await self.generate_test_messages(n)
        accepted, rejected = await self.service.ai_analyzer(messages)

        results: List[Dict[str, Any]] = []
        for msg in accepted:
            results.append({"text": msg.text, "offer": 1})
        for msg in rejected:
            results.append({"text": msg.text, "offer": 0})

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(results)} results to {self.output_file}")

    async def save_misclassified(
        self,
        test_messages: List[TelegramMessage],
        y_true: List[int],
        y_pred: List[int],
        probs: Optional[List[float]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Save misclassified test samples to a JSON file for later analysis.

        Returns the path written.
        """
        mis = []
        for msg, t, p in zip(test_messages, y_true, y_pred):
            if int(t) != int(p):
                entry: Dict[str, Any] = {
                    "text": msg.text if hasattr(msg, "text") else str(msg),
                    "true": int(t),
                    "pred": int(p)
                }
                if probs:
                    # probs may be per-class or confidence; try to attach if available
                    try:
                        entry["confidence"] = float(probs[len(mis)])
                    except Exception:
                        pass
                mis.append(entry)

        if not output_path:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_path = f"data\\logs\\misclassified_{now}.json"

        # ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(mis, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(mis)} misclassified records to {output_path}")
        return output_path

    def apply_balancing(self, X : list[TelegramMessage], y : list[int], strategy=BalancingStrategy.HYBRID, **kwargs):
        """
        Применяет балансировку ТОЛЬКО к обучающей выборке.
        """
        print(f"Балансировка: {strategy}")
        print(f"До балансировки: {Counter(y)}")
        
        if strategy == BalancingStrategy.NONE:
            return X, y

        if strategy == BalancingStrategy.HYBRID:
            # Получаем параметры или ставим дефолтные
            over = kwargs.get('over_strategy', 0.6)
            under = kwargs.get('under_strategy', 0.8)
            
            # SMOTE + RandomUnderSampler
            pipeline = Pipeline(steps=[
                ('o', SMOTE(sampling_strategy=over, random_state=42)),
                ('u', RandomUnderSampler(sampling_strategy=under, random_state=42))
            ])
            X_res, y_res = pipeline.fit_resample(X, y)

        elif strategy == BalancingStrategy.SIMPLE_UNDER:
            # Просто обрезаем мажоритарный класс до соотношения 1:1 (или другого)
            under_ratio = kwargs.get('under_strategy', 1.0) 
            rus = RandomUnderSampler(sampling_strategy=under_ratio, random_state=42)
            X_res, y_res = rus.fit_resample(X, y)
            
        else:
            raise ValueError(f"Неизвестная стратегия: {strategy}")

        print(f"  После балансировки: {Counter(y_res)}")
        return X_res, y_res

    async def train_balance_test_model(
        self,
        dataset_path: str,
        test_size: float = 0.2,
        random_state: int = 42,
        save_misclassified: bool = False,
        misclassified_output: Optional[str] = None,
    ):
        """
        Test RandomForestMessageClassifier.
        Load dataset, split, train and evaluate metrics.
        """

        # Load dataset
        print("Loading dataset...")
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = [TelegramMessage(text=item["text"]) for item in data]
        labels = [item["offer"] for item in data]

        X_train, X_test, y_train, y_test = train_test_split(
            messages, labels, test_size=test_size, random_state=random_state, stratify=labels
        )

        print(f"Dataset: {len(X_train)} train, {len(X_test)} test samples")

        # Balance training data
        clf = RandomForestMessageClassifier()

        X_train_vector = await clf._vectorize(X_train)
        
        X_train, y_train = self.apply_balancing(
            X_train_vector, y_train, strategy=BalancingStrategy.HYBRID, over_strategy=0.6, under_strategy=0.8)
        

        print("Training model...")
        await clf.train(X_train, y_train, to_vectorize=False)
        # await clf.save()

        def evaluate(y_true, y_pred, title: str):
            acc = accuracy_score(y_true, y_pred)
            prec = precision_score(y_true, y_pred, zero_division=0)
            rec = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            conf = confusion_matrix(y_true, y_pred)
            print(f"\n{title}")
            print(f"Accuracy : {acc:.4f}")
            print(f"Precision: {prec:.4f}")
            print(f"Recall   : {rec:.4f}")
            print(f"F1-score : {f1:.4f}")
            print("\nConfusion matrix:\n", conf)
            print("\nClassification report:\n", classification_report(y_true, y_pred, zero_division=0))
            return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "confusion_matrix": conf.tolist()}

        # 1) Raw model test
        print("Predicting with raw model...")
        preds_raw = await clf.predict(X_test)
        results_raw = evaluate(y_test, preds_raw, "Raw model results:")
        if save_misclassified:
            # save mismatches from the raw predictions
            await self.save_misclassified(X_test, y_test, preds_raw, output_path=misclassified_output)


        # 2) Model with filter and AI analysis
        service: TgFilterService = await TgFilterService.create(
            api_key=os.getenv("GEMINI_API_KEY"), ml_model_path=None, ml_model=clf
        )

        # Classify messages
        strict_accept, strict_reject, ambiguous = await service.classify_messages(X_test)
        gemini_accept, gemini_reject = await service.ai_analyzer(ambiguous)

        # Build predictions
        preds_filtered = []
        for msg in X_test:
            if msg in strict_accept or msg in gemini_accept:
                preds_filtered.append(1)
            elif msg in strict_reject or msg in gemini_reject:
                preds_filtered.append(0)
            else:
                raise ValueError(f"Message not classified: {msg.text[:50]}...")
            
        results_filtered = evaluate(y_test, preds_filtered, "Filtered model results:")
        if save_misclassified:
            # save mismatches from the filtered predictions
            await self.save_misclassified(X_test, y_test, preds_filtered, output_path=misclassified_output)



if __name__ == "__main__":
    async def main():
        # service = await TgFilterService.create(api_key=os.getenv("GEMINI_API_KEY"), ml_model_path="RF_model_2025-10-06_15-30-29.joblib")
        tester = ClassifyTester() #ClassifyTester(service)
        
        # await tester.get_test_sample(50000)
        await tester.train_balance_test_model("data\\training-ds\\dataset_balanced_2025-10-07_23-09-01.json", save_misclassified=True)
        # await tester.test_all_filter_service("data\\training-ds\\dataset_balanced_2025-10-07_23-09-01.json")

    asyncio.run(main())
