import os
import json
import asyncio
from typing import List, Tuple

from google import genai
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

from services.base import Service
from models import Container, TelegramChannel
from utils import get_prompt_by_id

class WebFilterService(Service):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite", strategy: str = "geo", target_region_set: set = {"Bayern"}):
        super().__init__()

        self.model = model
        self.client = genai.Client(api_key=api_key)
        self.strategy = strategy
        self.target_regions_set = target_region_set
        self.target_regions_set = {r.lower() for r in target_region_set}

        if self.strategy == "geo" or self.strategy == "hybrid":
            self.geolocator = Nominatim(user_agent="my_telegram_filter_bot_v1")


    async def run(self, container: Container) -> Container:
        """
        Loads TelegramChannel objects from JSON, classifies cities via Gemini,
        and returns only relevant channels (e.g., located in Bavaria).
        """
        channels: List[TelegramChannel] = container.channels

        cities_to_check = [c.city for c in channels]
        final_results = {}

        # 1. GEO PHASE
        if self.strategy in ["geo", "hybrid"]:
            print(f"[INFO] PHASE 1 - starting Geo classification for {len(cities_to_check)} cities...")
            geo_results, unresolved_cities = await self._classify_cities_geo(cities_to_check)
            final_results.update(geo_results)
        else:
            geo_results = {}
            unresolved_cities = cities_to_check

        # 2. LLM PHASE (Fallback)
        if unresolved_cities and self.strategy in ["llm", "hybrid"]:
            print(f"[INFO] PHASE 2 - sending {len(unresolved_cities)} unresolved cities to Gemini...")
            llm_results = await self._classify_cities_llm(unresolved_cities)
            final_results.update(llm_results)


        results = [
            channel for channel in channels
            if final_results.get(channel.city, False)
        ]
        return Container(channels=results)

    async def _classify_cities_geo(self, cities: List[str]) -> Tuple[dict[str, bool], List[str]]:
        """
        Validates cities using Nominatim (OpenStreetMap).
        Fast, free, but requires rate limiting (1 req/sec).
        """
        results: dict[str, bool] = {}
        unresolved: List[str] = []
        
        unique_cities = sorted(list(set(cities)))
        

        for city in unique_cities:
            try:
                location = await asyncio.to_thread(
                    self.geolocator.geocode, 
                    f"{city}, Germany", 
                    addressdetails=True,
                    language="de"
                )
                
                is_in_region = False
                if location:
                    address = location.raw.get('address', {})
                    state = address.get('state', '').lower()

                    if not state:
                        print(f"[WARN] Incomplete address info for {city}, defaulting to False")
                        unresolved.append(city)
                    else:
                        is_in_region = any(r in state for r in self.target_regions_set)
                                           
                else:
                    print(f"[WARN] No info for {city}, defaulting to False")
                    unresolved.append(city)
                
                results[city] = is_in_region
                
                await asyncio.sleep(1.0) 
                

            except (GeocoderTimedOut, GeocoderUnavailable):
                print(f"[ERROR] GeoAPI error for {city}, defaulting to False")
                results[city] = False
                unresolved.append(city)

        return results, unresolved

    async def _classify_cities_llm(self, cities: List[str]) -> dict[str, bool]:
        """Send unique city batches to Gemini and return mapping {city: bool}."""
        prompts_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "promts", "web_filter_service.json"
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

