import asyncio
import json
from typing import List, Optional, Set

from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import (
    UserAlreadyParticipantError, 
    InviteHashExpiredError, 
    UsernameNotOccupiedError, 
    FloodWaitError
)
import redis.asyncio as redis

from services.base import Service
from models import Container, TelegramChannel

MAX_JOIN_ATTEMPTS = 3


class TgMonitorService(Service):
    def __init__(
        self, 
        api_id: int, 
        api_hash: str, 
        password: str, 
        session_name: str = "anon-usr-vasa-monitor",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_queue: str = "telegram_messages",
        use_redis: bool = True
    ):
        super().__init__()

        self.client = TelegramClient(session_name, api_id, api_hash)
        self.password = password
        self.monitored_channels: Set[int] = set()  # Track channel IDs we're monitoring
        self._stop_event = asyncio.Event()

        self.use_redis = use_redis
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_queue = redis_queue
        self.redis_client: Optional[redis.Redis] = None

    async def __aenter__(self):
        await self.client.connect()
        
        # Check if already authorized
        if not await self.client.is_user_authorized():
            print("[INFO] Not authorized. Starting authentication...")
            
            # Start the authorization process
            await self.client.start()
            
            # If 2FA is enabled, provide password
            if self.password:
                try:
                    await self.client.sign_in(password=self.password)
                    print("[INFO] 2FA authentication successful.")
                except Exception as e:
                    print(f"[WARN] 2FA not needed or already authenticated: {e}")
        else:
            print("[INFO] Already authorized.")
        
        print("[INFO] Telegram client connected and authenticated.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client.is_connected():
            await self.client.disconnect()
            print("[INFO] Telegram monitor client disconnected.")

    async def _join_channel(self, url: str):
        """
        Attempt to join a channel/group.
        """
        for attempt in range(MAX_JOIN_ATTEMPTS):
            try:
                if "/+" in url or "joinchat" in url:
                    # Private invite
                    invite_hash = url.split("/")[-1].replace("+", "")
                    await self.client(ImportChatInviteRequest(invite_hash))
                else:
                    # Public channel
                    username = url.split("/")[-1]
                    await self.client(JoinChannelRequest(username))

                print(f"[INFO] Successfully joined {url}.")
                return

            except UserAlreadyParticipantError:
                # Not an error - expected behavior
                print(f"[INFO] Already a member of {url}.")
                return
            
            except (InviteHashExpiredError, UsernameNotOccupiedError) as e:
                print(f"[WARN] Could not join {url}: {e.__class__.__name__}:\n{e}")
                return

            except FloodWaitError as e:
                wait_time = e.seconds + 1
                print(f"[WARN] Flood wait of {wait_time}s required for {url} on attempt {attempt + 1}/{MAX_JOIN_ATTEMPTS}.")
                await asyncio.sleep(wait_time)

            except Exception as e:
                print(f"[ERROR] Unexpected error when trying to join {url}: {e}")
                await asyncio.sleep(5)
        
        print(f"[ERROR] Failed to join {url} after {MAX_JOIN_ATTEMPTS} attempts.")

    async def _send_to_redis(self, message_data: dict):
        """
        Send message to Redis queue.
        """
        if not self.redis_client:
            return
        
        try:
            message_json = json.dumps(message_data, default=str)
            await self.redis_client.rpush(self.redis_queue, message_json)
            print(f"[REDIS] Message sent to queue '{self.redis_queue}'")
        except Exception as e:
            print(f"[ERROR] Failed to send message to Redis: {e}")

    async def _handle_new_message(self, event):
        """
        Handler for new messages. Filters by keywords and sends to Redis queue.
        """
        msg = event.message
        
        if not msg.text:
            return
        
        try:
            # Get sender info
            sender = await msg.get_sender()
            sender_str = (
                f"@{sender.username}" if sender and sender.username
                else sender.phone if sender and sender.phone
                else "Unknown"
            )
            
            # Get channel info
            chat = await event.get_chat()
            channel_id = chat.id
            channel_name = getattr(chat, 'title', 'Unknown Channel')
            
            # Get metadata from our stored info
            channel_metadata = self.channel_info.get(channel_id, {})
            city = channel_metadata.get('city', 'Unknown')
            channel_url = channel_metadata.get('url', 'Unknown')
            
            # Prepare message data
            message_data = {
                'text': msg.text,
                'date': msg.date.isoformat(),
                'sender': sender_str,
                'channel_name': channel_name,
                'channel_url': channel_url,
                'city': city,
                'message_id': msg.id
            }
            
            # Print to console
            print(f"\n{'='*60}")
            print(f"[NEW MESSAGE] Channel: {channel_name} ({city})")
            print(f"[NEW MESSAGE] From: {sender_str}")
            print(f"[NEW MESSAGE] Date: {msg.date}")
            print(f"[NEW MESSAGE] Text: {msg.text[:200]}...")
            print(f"{'='*60}\n")
            
            # Send to Redis
            if self.use_redis:
                await self._send_to_redis(message_data)
            
        except Exception as e:
            print(f"[ERROR] Error handling message: {e}")

    async def run(self, container: Container) -> None:
        """
        Start monitoring all channels in the container.
        This runs indefinitely until stopped.
        """
        channels: List[TelegramChannel] = container.channels
        
        if not channels:
            print("[WARN] No channels to monitor.")
            return
        
        print(f"[INFO] Starting to monitor {len(channels)} channels...")
        
        # Join all channels first
        for channel in channels:
            try:
                await self._join_channel(channel.url)
                entity = await self.client.get_entity(channel.url)
                self.monitored_channels.add(entity.id)
                print(f"[INFO] Added {channel.name} ({channel.city}) to monitoring list.")
            except Exception as e:
                print(f"[ERROR] Could not add {channel.url} to monitoring: {e}")
        
        # Set up event handler for new messages in monitored channels
        @self.client.on(events.NewMessage(chats=list(self.monitored_channels)))
        async def message_handler(event):
            await self._handle_new_message(event)
        
        print(f"[INFO] Now monitoring {len(self.monitored_channels)} channels for new messages...")
        print("[INFO] Press Ctrl+C to stop monitoring.\n")
        
        # Keep running until stopped
        try:
            await self._stop_event.wait()
        except KeyboardInterrupt:
            print("\n[INFO] Monitoring stopped by user.")
    
    def stop(self):
        """
        Stop the monitoring service.
        """
        self._stop_event.set()