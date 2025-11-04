import os
from typing import Dict, Any, Callable, Awaitable
from dotenv import load_dotenv

from services.base import Service
from services.tg.parser_service import TgParserService
from services.tg.filter_service import TgFilterService
from services.tg.publisher_service import TgPublisherService

load_dotenv()

class ServiceFactory:
    """
    Асинхронная фабрика для создания экземпляров сервисов.
    Использует карту "строителей" (builder functions) для
    делегирования логики создания каждого конкретного сервиса.
    
    Это позволяет легко добавлять новые сервисы, не изменяя
    основной метод create_service (Принцип Открытости/Закрытости).
    """
    
    def __init__(self):
        """
        Инициализирует фабрику и регистрирует всех "строителей".
        """
        # Карта, сопоставляющая имя сервиса с асинхронным методом, который его создает
        self._builders: Dict[str, Callable[[Dict[str, Any]], Awaitable[Service]]] = {
            "TgParserService": self._build_parser_service,
            "TgFilterService": self._build_filter_service,
            "TgPublisherService": self._build_publisher_service,
        }


    async def create_service(self, name: str, params: Dict[str, Any]) -> Service:
        """
        Создает экземпляр сервиса по его имени, 
        находя и вызывая соответствующий асинхронный метод-строитель.
        """
        builder = self._builders.get(name)
        if not builder:
            raise ValueError(f"Unknown service name: {name}")

        try:
            # Делегируем создание сервиса специализированному методу
            return await builder(params)
        
        except KeyError as e:
            # Ошибка, если в .env нет нужного ключа или в config.json не хватает параметра
            print(f"[ERROR] Failed to create service '{name}'. Missing required parameter: {e}")
            raise
        except TypeError as e:
            # Ошибка, если __init__ сервиса не совпадает с тем, что мы передаем
            print(f"[ERROR] Could not create service '{name}'. Argument mismatch: {e}")
            raise
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred while creating service '{name}': {e}")
            raise

    # --- Методы-Строители (Builders) ---

    async def _build_parser_service(self, params: Dict[str, Any]) -> Service:
        """Строитель для TgParserService."""
        init_args = {
            'api_id': int(os.getenv("TG_API_ID")),
            'api_hash': os.getenv("TG_API_HASH"),
            'password': os.getenv("TG_PASSWORD"),
            'search_period_days': params['search_period_days']
        }

        # Параметры из конфига передаются, если они есть
        if 'session_name' in params:
            init_args['session_name'] = params['session_name']
        
        return TgParserService(**init_args)

    async def _build_filter_service(self, params: Dict[str, Any]) -> Service:
        """
        Асинхронный строитель для TgFilterService.
        Вызывает асинхронный `create` метод сервиса.
        """
        create_args = {
            'api_key': os.getenv("GEMINI_API_KEY"),
            'ml_model_path': params['ml_model_path']
        }
        
        # Необязательные параметры из config.json
        if 'ai_model' in params:
            create_args['ai_model'] = params['ai_model']
        if 'ml_model_name' in params:
            create_args['ml_model_name'] = params['ml_model_name']
        if 'confidence_threshold' in params:
            create_args['confidence_threshold'] = params['confidence_threshold']
        
        return await TgFilterService.create(**create_args)

    async def _build_publisher_service(self, params: Dict[str, Any]) -> Service:
        """Строитель для TgPublisherService."""
        init_args = {
            'bot_token': os.getenv("TG_BOT_TOKEN"),
            'channel_username': params['channel_username']
        }
        
        return TgPublisherService(**init_args)