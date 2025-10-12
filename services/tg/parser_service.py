from typing import List
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from services.base import Service
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

# период (4 месяца)
SEARCH_PERIOD = timedelta(days=30 * 3)


class TgParserService(Service):
    def __init__(self, api_id: int, api_hash: str, password: str, session_name: str = "anon-usr-vasa"):
        super().__init__()

        self.client = TelegramClient(session_name, api_id, api_hash)
        self.password = password

    async def _join_channel(self, url: str):
        """
        Попытка вступить в канал/группу.
        """
        try:
            if "/+" in url or "joinchat" in url:
                # приватный инвайт
                invite_hash = url.split("/")[-1].replace("+", "")
                await self.client(ImportChatInviteRequest(invite_hash))
            else:
                # публичный канал
                username = url.split("/")[-1]
                await self.client(JoinChannelRequest(username))
        except Exception as e:
            # возможно уже состоим или канал закрыт
            print(f"[WARN] Failed to join {url}: {e}")

    async def run(self, container: Container) -> Container:
        await self.client.start()
        cutoff_date = datetime.now() - SEARCH_PERIOD

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
                        if any(word in text for word in KEYWORDS):
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

        await self.client.disconnect()
        return Container(channels=channels)
