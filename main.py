import asyncio

from utils import load_channels
from orchestrator import Orchestrator
from models import Container, TelegramChannel

MAX_CONCURRENT_CHANNELS = 5  # ограничение параллельных подключений


async def process_channel(orchestrator: Orchestrator, channel: TelegramChannel, semaphore: asyncio.Semaphore) -> Container:
    async with semaphore:
        try:
            return await orchestrator.run(Container(channels=[channel]))
        except Exception as e:
            print(f"[ERROR] Failed to process channel {channel.url}: {e}")
            return Container(channels=[channel])  # возвращаем пустой канал


async def main():
    # Загружаем каналы
    initial_input = await load_channels("data\\FilterService\\2025-09-29_11-13-50.json")
    # initial_input.channels = initial_input.channels[:10]  # для теста

    async with await Orchestrator.create() as orchestrator:

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHANNELS)

        # Создаём задачи с ограничением параллелизма
        tasks = [process_channel(orchestrator, ch, semaphore) for ch in initial_input.channels]

        # Собираем результаты с обработкой исключений
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Логирование ошибок
        for r in results:
            if isinstance(r, Exception):
                print(f"[ERROR] Task failed: {r}")

        print("[INFO] Parsing completed.")

    # пройтись по всем пустым каналам и повторить попытку пропарсить
    # установить наблюдение за каждым каналом - если появляется соответственное сообщение - кидать его в группу.



# python -m cProfile -o profile_output.prof main.py
# snakeviz profile_output.prof

if __name__ == "__main__":
    asyncio.run(main())
