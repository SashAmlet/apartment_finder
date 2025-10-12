import datetime

from telegram import Bot
from telegram.constants import ParseMode

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
                    await self.bot.send_message(
                        chat_id=self.channel_username,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ Ошибка при публикации сообщения: {e}")

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
