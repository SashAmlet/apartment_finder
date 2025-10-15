import os
import copy
from datetime import datetime
from typing import Any
from dotenv import load_dotenv

from services.base import Service
from services.tg.parser_service import TgParserService
from services.tg.filter_service import TgFilterService
from services.tg.publisher_service import PublisherService

from models import Container

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
        for service in self.services:
            if hasattr(service, "__aenter__"):
                await service.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for service in self.services:
            if hasattr(service, "__aexit__"):
                await service.__aexit__(exc_type, exc_val, exc_tb)
        print("[INFO] All services properly closed.")

    async def run(self, initial_input: Any) -> dict[str, Container]:
        data = initial_input

        snapshots = {}

        for service in self.services:
            if not isinstance(service, Service):
                raise TypeError(f"{service} must inherit from Service")

            data = await service.run(data)
            snapshots[f"{service.__class__.__name__}"] = copy.deepcopy(data)

        return snapshots
