import datetime
import asyncio
import random

from telegram import Bot
from telegram.constants import ParseMode
from telethon.errors import FloodWaitError

from models import Container, TelegramChannel, TelegramMessage
from services.base import Service


class PublisherService(Service):
    """
    Сервис для публикации результатов анализа в Telegram-канал.
    """
    def __init__(self, bot_token: str, channel_username: str):
        """
        :param bot_token: токен Telegram-бота
        :param channel_username: публичный username канала, например '@my_public_results'
        """
        super().__init__()

        self.bot = Bot(token=bot_token)
        self.channel_username = channel_username

    @classmethod
    async def create(cls, bot_token: str, channel_username: str) -> "PublisherService":
        return cls(bot_token, channel_username)

    async def run(self, container: Container):
        """
        Публикует результаты из структуры Container в Telegram-канал.
        """
        for channel in container.channels:
            if not channel.messages:
                continue

            for msg in channel.messages:
                text = self._format_message(channel, msg)
                try:
                    
                    await self.safe_send_message(text)
                    await asyncio.sleep(random.uniform(1.5, 3.5))
                except Exception as e:
                    print(f"❌ Ошибка при публикации сообщения: {e}")


    async def safe_send_message(self, text: str, max_retries: int = 5):
        for attempt in range(1, max_retries + 1):
            try:
                await self.bot.send_message(
                    chat_id=self.channel_username,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                print("[INFO] Message sent successfully.")
                return

            except asyncio.TimeoutError:
                print(f"[WARN] Timeout — retrying ({attempt}/{max_retries})...")
                await asyncio.sleep(5 * attempt)  # экспоненциальная задержка

            except FloodWaitError as e:
                print(f"[WARN] Flood control: waiting {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
                # продолжаем с той же попытки после ожидания

            except Exception as e:
                print(f"[ERROR] Unexpected error on attempt {attempt}: {e}")
                await asyncio.sleep(2)

        print(f"[ERROR] Failed to send message after {max_retries} attempts.")


    def _format_message(self, channel: TelegramChannel, msg: TelegramMessage) -> str:
        """
        Формирует user-friendly текст публикации.
        """
        dt = msg.date.astimezone(datetime.timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
        sender_url = f"{msg.sender}" if msg.sender is not None else msg.sender
        return (
            f"<b>🏙️ Город:</b> {channel.city}\n"
            f"<b>📢 Канал:</b> <a href='{channel.url}'>{channel.name}</a>\n"
            f"<b>👤 Автор:</b> {sender_url}\n"
            f"<b>🕒 Дата:</b> {dt}\n\n"
            f"<b>💬 Сообщение:</b>\n{msg.text}"
        )
