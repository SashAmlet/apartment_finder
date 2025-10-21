from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from dataclasses_json import dataclass_json, config

@dataclass_json
@dataclass
class TelegramMessage:
    text: str
    sender: Optional[str] = None

    # Явно указываем, как обрабатывать datetime, чтобы избежать ошибок
    date: Optional[datetime] = field(
        default=None,
        metadata=config(
            # Encoder: как превратить datetime в JSON-совместимый тип
            encoder=lambda d: d.isoformat() if d else None,
            # Decoder: как из JSON-типа получить обратно datetime
            decoder=lambda s: datetime.fromisoformat(s) if s else None
        )
    )


@dataclass_json
@dataclass
class TelegramChannel:
    city: str
    name: str
    url: str
    messages: Optional[List[TelegramMessage]] = None


@dataclass_json
@dataclass
class Container:
    channels: List[TelegramChannel] 