from typing import Dict, Any
from services.base import Service
from services.tg.parser_service import TgParserService
from services.tg.filter_service import TgFilterService
from services.tg.publisher_service import TgPublisherService
# Импортируйте сюда все ваши сервисы

class ServiceFactory:
    def __init__(self):
        self._services = {
            "TgParserService": TgParserService,
            "TgFilterService": TgFilterService,
            "TgPublisherService": TgPublisherService,
            # Добавьте сюда другие сервисы
        }

    def create_service(self, name: str, params: Dict[str, Any]) -> Service:
        """
        Создает экземпляр сервиса по его имени и параметрам из конфига.
        """
        service_class = self._services.get(name)
        if not service_class:
            raise ValueError(f"Unknown service name: {name}")
        
        try:
            # **params "распаковывает" словарь в именованные аргументы
            return service_class(**params)
        except TypeError as e:
            print(f"[ERROR] Could not create service '{name}' with params {params}.")
            print(f"      Check if the parameters in config.json match the __init__ method of the service.")
            raise e
