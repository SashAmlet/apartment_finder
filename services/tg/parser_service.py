import asyncio
from typing import List
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError, InviteHashExpiredError, UsernameNotOccupiedError, FloodWaitError

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

MAX_JOIN_ATTEMPTS = 3

class TgParserService(Service):
    def __init__(self, api_id: int, api_hash: str, password: str, search_period_days: int, session_name: str = "anon-usr-vasa"):
        super().__init__()

        self.client = TelegramClient(session_name, api_id, api_hash)
        self.password = password
        self.search_period = timedelta(days=search_period_days)

    async def __aenter__(self):
        await self.client.connect()
        print("[INFO] Telegram client connected.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client.is_connected():
            await self.client.disconnect()
            print("[INFO] Telegram client disconnected.")

    async def _join_channel(self, url: str):
        """
        Попытка вступить в канал/группу.
        """
        for attempt in range(MAX_JOIN_ATTEMPTS):
            try:
                if "/+" in url or "joinchat" in url:
                    # приватный инвайт
                    invite_hash = url.split("/")[-1].replace("+", "")
                    await self.client(ImportChatInviteRequest(invite_hash))
                else:
                    # публичный канал
                    username = url.split("/")[-1]
                    await self.client(JoinChannelRequest(username))

                print(f"[INFO] Successfully joined {url}.")
                return

            except UserAlreadyParticipantError:
                # ЭТО НЕ ОШИБКА! Это ожидаемое поведение. Логируем как INFO.
                # print(f"[INFO] Already a member of {url}. Skipping join.")
                return
            
            except (InviteHashExpiredError, UsernameNotOccupiedError) as e:
                # Это реальные проблемы с каналом, которые стоит отметить.
                print(f"[WARN] Could not join {url}: {e.__class__.__name__}:\n{e}")
                return

            except FloodWaitError as e:
                # Telegram просит подождать.
                wait_time = e.seconds + 1 # +1 секунда на всякий случай
                print(f"[WARN] Flood wait of {wait_time}s required for {url} on attempt {attempt + 1}/{MAX_JOIN_ATTEMPTS}.")
                await asyncio.sleep(wait_time)

            except Exception as e:
                # Все остальные, неожиданные ошибки.
                print(f"[ERROR] An unexpected error occurred when trying to join {url}: {e}")
                await asyncio.sleep(5)
        
        print(f"[ERROR] Failed to join {url} after {MAX_JOIN_ATTEMPTS} attempts.")

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

        return Container(channels=channels)
