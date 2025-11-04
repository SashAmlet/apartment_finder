import re
import os
import json
import asyncio
from typing import List, Tuple

from google import genai

from models import Container, TelegramChannel, TelegramMessage
from utils import get_prompt_by_id

from services.base import Service
from services.tg.classifier.base import Classifier
from services.tg.classifier.random_forest import RandomForestMessageClassifier


class TgFilterService(Service):
    """
    Класс для фильтрации Telegram-сообщений об аренде.
    Двухуровневая система:
      1. Жесткий (strict) препроцессинг на основе правил.
      2. Проверка сомнительных сообщений через внешний AI (например, Google Gemini).
    """

    def __init__(self, api_key: str, ai_model: str, ml_model: Classifier, confidence_threshold: float = .8):
        super().__init__()
        
        self.ai_model = ai_model
        self.client = genai.Client(api_key=api_key)
        self.ml_model = ml_model
        self.confidence_threshold = confidence_threshold

    @classmethod
    async def create(cls, api_key: str, ml_model_path: str, ml_model = None, ml_model_name: str="RandomForest", ai_model: str = "gemini-2.5-flash-lite", confidence_threshold: float = .8) -> "TgFilterService":
        
        if ml_model is None:
            if ml_model_name == "RandomForest":
                ml_model = RandomForestMessageClassifier()

            ml_model_path = os.path.join(os.path.dirname(__file__), "..", "..", ml_model_path)
            await ml_model.load(ml_model_path)
        else:
            assert isinstance(ml_model, Classifier), "ml_model must be an instance of Classifier"

        return cls(api_key, ai_model, ml_model, confidence_threshold)


    async def run(self, container: Container) -> Container:
        """
        Главный метод:
        1. Делит сообщения на strict_accept / reject / ambiguous.
        2. Обрабатывает ambiguous через Gemini.
        3. Возвращает итоговый список strict_accept.
        """
        all_channels = []
        channels: List[TelegramChannel] = container.channels

        for channel in channels:
            if not channel.messages:
                all_channels.append(channel)
                continue
            
            strict_accept: List[TelegramMessage] = []
            ambiguous: List[TelegramMessage] = []

            # Классификация сообщений канала
            strict_accept, rej, ambiguous = await self.classify_messages(channel.messages)

            # Обработка сомнительных сообщений через Gemini
            gemini_accept: List[TelegramMessage] = []
            if ambiguous:
                gemini_accept, _ = await self.ai_analyzer(ambiguous)

            # Формируем итог
            channel.messages = strict_accept + gemini_accept
            all_channels.append(channel)

        return Container(channels=all_channels)



    async def classify_messages(
        self, messages: List[TelegramMessage]
    ) -> Tuple[List[TelegramMessage], List[TelegramMessage], List[TelegramMessage]]:
        """
        Классифицирует список сообщений.
        Возвращает кортеж:
          (strict_accept, reject, ambiguous)
        """
        accept, reject, ambiguous = [], [], []

        pred_result = await self.ml_model.predict_with_confidence(messages)

        for msg, res in zip(messages, pred_result):
            if res["confidence"] >= self.confidence_threshold:
                if res["class"] == 1:
                    accept.append(msg)
                else:
                    reject.append(msg)
            else:
                ambiguous.append(msg)

        return accept, reject, ambiguous
    
    def _clean_ai_response_text(self, raw_text: str) -> str:
        """
        Очищает текст ответа модели от мусора, неправильных экранирований и
        подготавливает к JSON-десериализации.
        """
        if not raw_text:
            return ""

        cleaned = raw_text.strip()

        # 1️⃣ Удаляем Markdown/LLM-маркеры вроде ```json``` или ```
        cleaned = re.sub(r"(?s)```json|```", "", cleaned).strip()

        # 2️⃣ Поправляем некорректные escape-последовательности
        # (заменяем одинарные обратные слэши на двойные, кроме допустимых)
        cleaned = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', cleaned)
        cleaned = cleaned.replace('\\\\\"', '\\"')

        # 3️⃣ Экранируем кавычки внутри "text"
        cleaned = re.sub(
            r'("text":\s*")((?:[^"\\]|\\.)*)"',
            lambda m: '"text": "{}"'.format(m.group(2).replace('"', r'\"')),
            cleaned
        )

        return cleaned
    
    async def ai_analyzer(self, messages: List[TelegramMessage]) -> Tuple[List[TelegramMessage], List[TelegramMessage]]:
        """
        Использует Google Gemini для анализа сообщений пакетами по 5.
        Возвращает только те сообщения, которые действительно относятся к сдаче жилья.
        """

        if not messages:
            return []

        prompts_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "promts", "tg_filter_service.json"
        )
        system, user_template = get_prompt_by_id(prompts_path, "1")

        accepted = []
        rejected = []
        batch_size = 10

        # разбиваем на батчи по batch_size сообщений
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]

            # формируем user-промт
            batch_texts = []
            for idx, msg in enumerate(batch, start=1):
                batch_texts.append(f'{idx}) id: {msg.sender}, text: "{msg.text}"')
            user = user_template.format(input_data=batch_texts)

            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.ai_model,
                    contents=[system, user],
                )

                raw_text = response.text.strip()

                # 🧹 Удаляем LLM-маркеры и мусор
                cleaned = self._clean_ai_response_text(raw_text) 

                # 🧩 Ищем JSON-массив в тексте
                match = re.search(r"\[.*\]", cleaned, re.DOTALL)
                if not match:
                    print(f"⚠️ JSON массив не найден в ответе батча {i//batch_size + 1}")
                    continue

                json_text = match.group(0)

                try:
                    result_json = json.loads(json_text)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSONDecodeError в батче {i//batch_size + 1}: {e}")
                    print(f"⚙️ Пробуем через eval-защищённый парсинг...")
                    # Попытка парсинга fallback-способом
                    safe_text = json_text.replace("'", '"')
                    result_json = json.loads(safe_text)

                for obj, msg in zip(result_json, batch):
                    if obj.get("offer"):
                        accepted.append(msg)
                    else:
                        rejected.append(msg)

            except Exception as e:
                print(f"ai_analyzer ERROR::\n {i//10 + 1}: {e}\n{response.text if 'response' in locals() else ''}")

        return accepted, rejected
    