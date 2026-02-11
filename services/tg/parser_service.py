import asyncio
from typing import List
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError, InviteHashExpiredError, UsernameNotOccupiedError, FloodWaitError

from services.tg.base import TelegramServiceBase
from models import Container, TelegramChannel, TelegramMessage


KEYWORDS = [
    # RU
    "сдаю", "квартира", "аренда", "жильё", "комната",
    # UA
    "здаю", "квартира", "оренда", "житло", "кімната",
    # EN
    "apartment", "house", "room", "rent",
    # DE
    "wohnung", "miete", "zimmer", "unterkunft", "haus"
]

MAX_JOIN_ATTEMPTS = 3

class TgParserService(TelegramServiceBase):
    def __init__(self, api_id: int, api_hash: str, password: str, search_period_days: int, session_name: str = "anon-usr-vasa"):
        super().__init__(api_id, api_hash, password, session_name)

        self.search_period = timedelta(days=search_period_days)

    async def run(self, container: Container) -> Container:
        cutoff_date = datetime.now() - self.search_period

        channels: List[TelegramChannel] = container.channels

        for channel in channels:
            try:
                # вступаем перед парсингом
                await self._join_channel(channel.url)

                entity = await self.client.get_entity(channel.url)
                messages = []
                async for msg in self.client.iter_messages(entity, offset_date=cutoff_date, reverse=True):
                    if msg.text:
                        text = msg.text.lower()
                        if 1:#any(word in text for word in KEYWORDS):
                            sender = await msg.get_sender()  # Получаем объект User
                            
                            sender_str = (
                                f"@{sender.username}" if sender and sender.username
                                else sender.phone if sender and sender.phone
                                else "Unknown"
                            )

                            messages.append(
                                TelegramMessage(
                                    text=msg.text,
                                    date=msg.date,
                                    sender=sender_str,
                                )
                            )
                channel.messages = messages
            except Exception as e:
                print(f"[ERROR] Error while processing {channel.url}: {e}")
                channel.messages = []

        return Container(channels=channels)
