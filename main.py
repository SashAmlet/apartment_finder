import asyncio
from typing import List

from utils import load_channels
from orchestrator import Orchestrator
from models import Container, TelegramChannel

async def process_channel(orchestrator: Orchestrator, channel: TelegramChannel) -> Container:
    return await orchestrator.run(Container(channels=[channel]))

async def main():
    initial_input = await load_channels("data\\FilterService\\2025-09-29_11-13-50.json")
    # initial_input.channels = initial_input.channels[:1]

    orchestrator = await Orchestrator.create()

    # Создаём отдельную задачу для каждого канала
    tasks = [process_channel(orchestrator, ch) for ch in initial_input.channels]

    # Запускаем параллельно
    results = await asyncio.gather(*tasks)
    
    # пройтись по всем пустым каналам и повторить попытку пропарсить
    # установить наблюдение за каждым каналом - если появляется соответственное сообщение - кидать его в группу.
    

asyncio.run(main())

# python -m cProfile -o profile_output.prof main.py
# snakeviz profile_output.prof