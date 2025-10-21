import datetime
import asyncio
import random

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter


from models import Container, TelegramChannel, TelegramMessage
from services.base import Service


class TgPublisherService(Service):
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

    async def run(self, container: Container) -> Container:
        """
        Публикует результаты из структуры Container в Telegram-канал.
        """
        not_sent_container = Container(channels=[])

        for channel in container.channels:
            if not channel.messages:
                continue

            not_sent_msgs = []
            for msg in channel.messages:
                text = self._format_message(channel, msg)
                try:
                    if not await self.safe_send_message(text):
                        not_sent_msgs.append(msg)

                    await asyncio.sleep(random.uniform(1.5, 3.5))
                except Exception as e:
                    print(f"❌ Ошибка при публикации сообщения: {e}")
                    not_sent_msgs.append(msg)

            if not_sent_msgs:
                existing = next((ch for ch in not_sent_container.channels if ch.url == channel.url), None)
                if existing:
                    existing.messages.extend(not_sent_msgs)
                else:
                    not_sent_channel = TelegramChannel(
                        name=channel.name,
                        url=channel.url,
                        city=channel.city,
                        messages=not_sent_msgs
                    )
                    not_sent_container.channels.append(not_sent_channel)

        return not_sent_container



    async def safe_send_message(self, text: str, max_retries: int = 5) -> bool:
        for attempt in range(1, max_retries + 1):
            try:
                await self.bot.send_message(
                    chat_id=self.channel_username,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                # print("[INFO] Message sent successfully.")
                return True

            except asyncio.TimeoutError:
                print(f"[WARN] Timeout — retrying ({attempt}/{max_retries})...")
                await asyncio.sleep(5 * attempt)  # экспоненциальная задержка

            except RetryAfter as e:
                print(f"[WARN] Flood control: waiting {e.retry_after} seconds...")
                await asyncio.sleep(e.retry_after)
                # продолжаем с той же попытки после ожидания

            except Exception as e:
                print(f"[ERROR] Unexpected error on attempt {attempt}: {e}")
                # print(f"[DEBUG] Exception type: {type(e)} | Module: {type(e).__module__}")
                await asyncio.sleep(2)

        print(f"[ERROR] Failed to send message after {max_retries} attempts.")
        return False


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
