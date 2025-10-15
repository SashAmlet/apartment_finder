from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class TelegramMessage:
    text: str
    date: Optional[datetime] = None
    sender: Optional[str] = None


@dataclass
class TelegramChannel:
    city: str
    name: str
    url: str
    messages: Optional[List[TelegramMessage]] = None


@dataclass
class Container:
    channels: List[TelegramChannel] 