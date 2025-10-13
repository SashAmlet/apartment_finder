import json
import aiofiles
from typing import Tuple

from models import TelegramChannel, Container

def get_prompt_by_id(promt_path: str, prompt_id: str) -> Tuple[str, str]:
    """
    Reads a JSON file with prompts, searches for a prompt by the given ID
    and returns system and user as strings.

    :param promt_path: path to the JSON file with prompts
    :param prompt_id: ID of the required prompt
    :return: tuple (system_text, user_text)
    :raises ValueError: if a prompt with such ID is not found
    """
    with open(promt_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    prompts = data.get("prompts", [])
    
    for prompt in prompts:
        if prompt.get("id") == prompt_id:
            system_text = "\n".join(prompt.get("system", []))
            user_text = "\n".join(prompt.get("user", []))
            return system_text, user_text
    
    raise ValueError(f"Prompt with id '{prompt_id}' not found in {promt_path}")


async def load_channels(input_file: str) -> Container:
    """Загружает список каналов из JSON-файла (где объекты сериализованы строками)."""
    async with aiofiles.open(input_file, "r", encoding="utf-8") as f:
        raw = await f.read()
    data = json.loads(raw)

    # eval преобразует строки "TelegramChannel(...)" обратно в объекты
    channels = [eval(item) for item in data["channels"]]

    return Container(channels=channels)