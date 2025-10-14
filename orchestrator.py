import os
import json
from datetime import datetime
from dataclasses import is_dataclass, asdict
from typing import Any
from dotenv import load_dotenv

from services.base import Service
from services.tg.parser_service import TgParserService
from services.tg.filter_service import TgFilterService
from services.tg.publisher_service import PublisherService

load_dotenv() 

class Orchestrator:
    def __init__(self, services):
        self.services = services
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.save_cache = {} 
        self.base_folder = "data"

    @classmethod
    async def create(cls):
        tg_parser = TgParserService(
            api_id=os.getenv("TG_API_ID"),
            api_hash=os.getenv("TG_API_HASH"),
            password=os.getenv("TG_PASSWORD")
        )
        tg_filter = await TgFilterService.create(
            api_key=os.getenv("GEMINI_API_KEY"),
            ml_model_path="RF_model_2025-10-07_23-15-48.joblib"
        )
        tg_publisher = PublisherService(
            bot_token=os.getenv("TG_BOT_TOKEN"),
            channel_username=os.getenv("TG_CHANNEL_USERNAME")
        )

        return cls([tg_parser, tg_filter, tg_publisher])

    async def __aenter__(self):
        # подключаем клиента Telegram при входе в контекст
        for service in self.services:
            if hasattr(service, "__aenter__"):
                await service.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for service in self.services:
            if hasattr(service, "__aexit__"):
                await service.__aexit__(exc_type, exc_val, exc_tb)
        print("[INFO] All services properly closed.")

    async def run(self, initial_input: Any) -> Any:
        data = initial_input

        for service in self.services:
            if not isinstance(service, Service):
                raise TypeError(f"{service} must inherit from Service")

            data = await service.run(data)
            await self.save(service, data)

        return data

    async def save(self, service: 'Service', data: Any):
        """
        Сохраняет результаты выполнения всех сервисов в один файл в рамках одной сессии.
        """
        service_name = service.__class__.__name__
        folder_path = os.path.join(self.base_folder, "SessionResults")
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, f"{self.timestamp}.json")

        # Подготовка: рекурсивная конвертация dataclass -> dict
        def convert(obj):
            if is_dataclass(obj):
                return {k: convert(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, list):
                return [convert(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        clean = convert(data)
        self.save_cache[service_name] = clean  # сохраняем в кэш по названию сервиса

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.save_cache, f, ensure_ascii=False, indent=4)
            print(f"[INFO] Saved unified result: {file_path}")
        except Exception as e:
            print(f"[ERROR] Could not save result for {service_name}: {e}")
