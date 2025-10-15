import os
import json
import aiofiles
from datetime import datetime
from dataclasses import is_dataclass, asdict

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

class DataManager:
    def __init__(self, base_dir: str = "data/SessionResults"):
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_path = os.path.join(base_dir, self.session_timestamp)
        os.makedirs(self.session_path, exist_ok=True)
        print(f"[INFO] DataManager initialized. Session path: {self.session_path}")

    async def save_snapshot(self, filename: str, data: Container):
        """
        Асинхронно сохраняет контейнер с датаклассами в JSON-файл,
        используя кастомный кодировщик.
        """
        file_path = os.path.join(self.session_path, filename)
        
        json_data = json.dumps(data, indent=4, cls=DataclassJSONEncoder, ensure_ascii=False)

        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json_data)
        print(f"[INFO] Snapshot saved to {file_path}")

    def get_session_path(self) -> str:
        return self.session_path