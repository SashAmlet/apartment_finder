import os
import json
import asyncio
from typing import List

from google import genai

from services.base import Service
from models import Container, TelegramChannel
from utils import get_prompt_by_id

class WebFilterService(Service):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite"):
        super().__init__()

        self.model = model
        self.client = genai.Client(api_key=api_key)

    async def run(self, container: Container) -> Container:
        """
        Loads TelegramChannel objects from JSON, classifies cities via Gemini,
        and returns only relevant channels (e.g., located in Bavaria).
        """
        channels: List[TelegramChannel] = container.channels

        gemini_outputs = await self._classify_cities([c.city for c in channels])

        results = [
            channel for channel in channels
            if gemini_outputs.get(channel.city, False)
        ]
        return Container(channels=results)

    async def _classify_cities(self, cities: List[str]) -> dict[str, bool]:
        """Send unique city batches to Gemini and return mapping {city: bool}."""
        prompts_path = os.path.join(
            os.path.dirname(__file__), "..", "promts", "web_filter_service.json"
        )
        system, user_template = get_prompt_by_id(prompts_path, "1")

        results: dict[str, bool] = {}
        batch_size = 10

        # уникализируем города
        unique_cities = sorted(list(set(cities)))

        for i in range(0, len(unique_cities), batch_size):
            batch = unique_cities[i:i + batch_size]
            user = user_template.format(input_data=batch)

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[system, user],
            )

            parsed = json.loads(response.candidates[0].content.parts[0].text)
            results.update(parsed)

        return results

