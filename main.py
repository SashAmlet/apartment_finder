import asyncio
from collections import defaultdict
from typing import Dict

from utils import load_channels
from orchestrator import Orchestrator
from models import Container, TelegramChannel
from data_manager import DataManager  # Используем наш DataManager

MAX_CONCURRENT_CHANNELS = 5

async def process_channel(orchestrator: Orchestrator, channel: TelegramChannel, semaphore: asyncio.Semaphore) -> Dict[str, Container]:
    async with semaphore:
        try:
            return await orchestrator.run(Container(channels=[channel]))
        except Exception as e:
            print(f"[ERROR] Failed to process channel {channel.url}: {e}")
            return {}

async def main():
    data_manager = DataManager()
    initial_input = await load_channels("data\\FilterService\\2025-09-29_11-13-50.json")

    initial_input.channels = initial_input.channels[:3]

    async with await Orchestrator.create() as orchestrator:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHANNELS)
        tasks = [process_channel(orchestrator, ch, semaphore) for ch in initial_input.channels]
        # results - это список словарей, где каждый словарь - отчет по одному каналу
        results = await asyncio.gather(*tasks, return_exceptions=True)

    print("[INFO] All channels processed. Aggregating intermediate results...")

    # 2. Агрегируем результаты. defaultdict упрощает код.
    # Ключ - имя сервиса, значение - объединенный контейнер для этого сервиса
    aggregated_snapshots = {}
    error_count = 0

    for res in results:
        if isinstance(res, dict):
            for service_name, container_snapshot in res.items():
                # Добавляем данные из снепшота в общий агрегированный контейнер

                if service_name not in aggregated_snapshots:
                    aggregated_snapshots[service_name] = Container(channels=[])

                aggregated_snapshots[service_name].channels.extend(container_snapshot.channels)
                # Можно также добавить каналы, если это нужно для контекста
                # aggregated_snapshots[service_name].channels.extend(container_snapshot.channels)
        elif isinstance(res, Exception):
            error_count += 1
            print(f"[ERROR] A task failed with exception: {res}")

    print(f"[INFO] Aggregation complete. Errors: {error_count}.")

    # 3. Сохраняем каждый агрегированный снепшот в отдельный файл
    for service_name, final_container in aggregated_snapshots.items():
        filename = f"{service_name}_snapshot.json"
        await data_manager.save_snapshot(filename, final_container)
    
    print(f"[INFO] All snapshots saved. Results are in: {data_manager.get_session_path()}")

    # если канал уже был пропарсен за дата\время - пропускаем эту дату\время
    # Распознаватель земли работает паршиво
    # Улучшить фильтратор сообщений
    # установить наблюдение за каждым каналом - если появляется соответственное сообщение - кидать его в группу.



# python -m cProfile -o profile_output.prof main.py
# snakeviz profile_output.prof

if __name__ == "__main__":
    asyncio.run(main())
