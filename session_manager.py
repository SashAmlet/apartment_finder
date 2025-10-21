import os
import json
import aiofiles
from datetime import datetime
from dataclasses import is_dataclass, asdict
from typing import Optional

from models import Container

class DataclassJSONEncoder(json.JSONEncoder):
    """
    Специальный JSON-кодировщик, который умеет обрабатывать:
    - Объекты dataclass (преобразуя их в словари)
    - Объекты datetime (преобразуя их в строки формата ISO)
    """
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

class SessionManager:
    def __init__(self, base_dir: str = "data/SessionResults"):
        self.base_path = base_dir
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_path = os.path.join(self.base_path, self.session_timestamp)
        os.makedirs(self.session_path, exist_ok=True)
        print(f"[INFO] SessionManager initialized. Current session path: {self.session_path}")

    def find_session_path(self, session_id: str) -> Optional[str]:
        """Находит путь к сессии по ID ('latest' или 'YYYY-MM-DD_HH-MM-SS')."""
        if session_id == "latest":
            # 1. Получаем список всех директорий сессий
            all_sessions = sorted([
                d for d in os.listdir(self.base_path) 
                if os.path.isdir(os.path.join(self.base_path, d))
            ])

            # 2. Исключаем из списка папку ТЕКУЩЕЙ сессии
            current_session_name = os.path.basename(self.session_path)
            completed_sessions = [s for s in all_sessions if s != current_session_name]
            
            # 3. Если после фильтрации остались завершенные сессии, берем последнюю
            if not completed_sessions:
                print("[WARN] No previous completed sessions found to use as 'latest'.")
                return None
            
            latest_completed_path = os.path.join(self.base_path, completed_sessions[-1])
            print(f"[INFO] Found 'latest' completed session: {latest_completed_path}")
            return latest_completed_path
        else:
            path = os.path.join(self.base_path, session_id)
            return path if os.path.isdir(path) else None

    async def load_snapshot(self, session_path: str, service_name: str) -> Optional[Container]:
        """Загружает артефакт (снепшот) конкретного сервиса из указанной сессии."""
        file_path = os.path.join(session_path, f"{service_name}_snapshot.json")
        
        if not os.path.exists(file_path):
            return None
            
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return Container.from_json(content)
        except Exception as e:
            print(f"[ERROR] Failed to load snapshot {file_path}: {e}")
            return None

    async def save_snapshot(self, service_name: str, data: Container):
        """Сохраняет снепшот в директорию ТЕКУЩЕЙ сессии."""
        filename = f"{service_name}_snapshot.json"
        file_path = os.path.join(self.session_path, filename)
        
        json_data = json.dumps(data, indent=4, cls=DataclassJSONEncoder, ensure_ascii=False)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json_data)
        print(f"[INFO] Snapshot for '{service_name}' saved to {file_path}")