import asyncio
import json
from models import Container
from orchestrator import Orchestrator
from session_manager import SessionManager
from utils import load_channels # Ваш существующий загрузчик

async def main():
    """
    Главная точка входа в приложение.
    Загружает конфигурацию, инициализирует сервисы и запускает оркестратор.
    """
    # 1. Загружаем конфигурацию пайплайна
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("[ERROR] config.json not found! Please create a configuration file.")
        return
    except json.JSONDecodeError:
        print("[ERROR] Could not parse config.json. Please check for syntax errors.")
        return

    # 2. Инициализируем менеджер сессий для этого конкретного запуска
    session_manager = SessionManager()

    # 3. Загружаем начальные данные для пайплайна.
    # В нашем случае, это список каналов из предыдущего этапа.
    try:
        initial_data = await load_channels("data/FilterService/2025-09-29_11-13-50.json")
    except FileNotFoundError:
        print("[WARN] Initial data file not found. Starting with an empty container.")
        initial_data = Container(channels=[], messages=[])

    # 4. Создаем и запускаем Оркестратор, который будет управлять всем процессом
    orchestrator = Orchestrator(config, session_manager)
    await orchestrator.run(initial_data)

if __name__ == "__main__":
    asyncio.run(main())

