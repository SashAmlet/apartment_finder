import os
import json
from typing import Any
from datetime import datetime
from dotenv import load_dotenv
from dataclasses import asdict, is_dataclass

from services.base import Service
from services.tg.parser_service import TgParserService
from services.tg.filter_service import TgFilterService
from services.tg.publisher_service import PublisherService


load_dotenv()

class Orchestrator:
    def __init__(self, services):
        self.services = services


    @classmethod
    async def create(cls):
        services = [
            TgParserService(api_id=os.getenv("TG_API_ID"), api_hash=os.getenv("TG_API_HASH"), password=os.getenv("TG_PASSWORD")),
            await TgFilterService.create(api_key=os.getenv("GEMINI_API_KEY"), ml_model_path="RF_model_2025-10-07_23-15-48.joblib"),
            PublisherService(bot_token = os.getenv("TG_BOT_TOKEN"), channel_username = os.getenv("TG_CHANNEL_USERNAME")),
        ]
        return cls(services)

    async def run(self, initial_input: Any) -> Any:
        """
        Pipeline launch of services:
        - Passes the result of one service to the next
        - Returns the final result after the last service
        """
        data = initial_input

        for service in self.services:
            if not isinstance(service, Service):
                raise TypeError(f"{service} must inherit from Service")
            
            data = await service.run(data)
            await self.save(service, data)


        return data
    
    async def save(self, service: Service, data: Any):
        service_name = service.__class__.__name__
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder_path = os.path.join("data", service_name)
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, f"{timestamp}.json")

        # Подготовка: если data — dataclass или содержит dataclass, преобразуем в структуры
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

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=4)
            print(f"[INFO] Saved intermediate result: {file_path}")
        except Exception as e:
            print(f"[ERROR] Could not save result for {service_name}: {e}")