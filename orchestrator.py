import copy
from typing import Any, Dict
from models import Container
from service_factory import ServiceFactory
from session_manager import SessionManager

class Orchestrator:
    """
    Управляет выполнением пайплайна сервисов на основе конфигурационного файла.
    Поддерживает опциональное переиспользование артефактов (кэша)
    из предыдущих запусков (сессий).
    """
    def __init__(self, config: Dict, session_manager: SessionManager):
        """
        Инициализируется конфигурацией пайплайна и менеджером сессий.
        """
        self.pipeline_config = config.get('pipeline', [])
        self.run_config = config.get('run_config', {})
        self.session_manager = session_manager
        self.service_factory = ServiceFactory()
        print("[Orchestrator] Initialized with config-driven pipeline.")

    async def run(self, initial_input: Container) -> None:
        """
        Выполняет пайплайн, определенный в конфигурационном файле.
        """
        current_data = initial_input
        
        source_session_id = self.run_config.get('source_session_id', 'none')
        source_session_path = self.session_manager.find_session_path(source_session_id)

        if source_session_path:
            print(f"[INFO] Using source session for cache: {source_session_path}")
        else:
            print(f"[WARN] Source session '{source_session_id}' not found. Cache will not be used.")

        for step_config in self.pipeline_config:
            service_name = step_config['service']
            use_cache = step_config.get('use_cache', False)
            
            cached_data = None
            if use_cache and source_session_path:
                print(f"[INFO] Attempting to load cached snapshot for '{service_name}'...")
                cached_data = await self.session_manager.load_snapshot(source_session_path, service_name)

            if cached_data:
                print(f"[INFO] >>> Cache HIT for '{service_name}'. Skipping execution.")
                current_data = cached_data
            else:
                if use_cache:
                    print(f"[INFO] >>> Cache MISS for '{service_name}'. Running service.")
                
                # Создаем сервис с параметрами из конфига
                service = self.service_factory.create_service(
                    name=service_name, 
                    params=step_config.get('params', {})
                )

                # Запускаем реальную логику сервиса
                current_data = await service.run(current_data)
            
            # Сохраняем результат (новый или из кэша) как артефакт ТЕКУЩЕЙ сессии
            await self.session_manager.save_snapshot(service_name, copy.deepcopy(current_data))

        print("\n[INFO] Pipeline finished successfully.")
        print(f"[INFO] All artifacts for this run are saved in: {self.session_manager.session_path}")
