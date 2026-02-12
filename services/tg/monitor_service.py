import asyncio
import json
from typing import List, Optional

from telethon import events

from redis import asyncio as aioredis

from services.tg.base import TelegramServiceBase
from utils.message_tracker import MessageOffsetTracker
from models import Container, TelegramChannel

MAX_JOIN_ATTEMPTS = 3


class TgMonitorService(TelegramServiceBase):
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
        use_redis: bool = True,
        offset_storage_path: str = "data/monitor_offsets.json"
    ):
        super().__init__(api_id, api_hash, password, session_name)

        self.monitored_channels: dict = {}  # Track channel IDs we're monitoring
        self._stop_event = asyncio.Event()

        self.use_redis = use_redis
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_queue = redis_queue
        self.redis_client: Optional[aioredis.Redis] = None
        
        # Offset tracking for message persistence
        self.offset_tracker = MessageOffsetTracker(offset_storage_path)
        
        # Track if we've processed catchup messages
        self._catchup_done = set()

    async def __aenter__(self):
        await super().__aenter__()

        # Initialize Redis connection if enabled
        if self.use_redis:
            self.redis_client = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            print(f"[INFO] Connected to Redis at {self.redis_host}:{self.redis_port}")
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup connections."""
        if self.redis_client:
            await self.redis_client.close()
            print("[INFO] Redis connection closed.")
        
        await super().__aexit__(exc_type, exc_val, exc_tb)

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

    async def _process_message(self, msg, channel_id: int, update_offset: bool = True):
        """
        Process a single message: filter by keywords, send to Redis, update offset.
        """
        if not msg.text:
            return
        
        last_processed_id = self.offset_tracker.get_offset(channel_id)
        if last_processed_id and msg.id <= last_processed_id:
            # print(f"[INFO] Skipping duplicate message {msg.id} for channel {channel_id}")
            return
        
        try:
            # Get sender info
            sender = await msg.get_sender()
            sender_str = (
                f"@{sender.username}" if sender and sender.username
                else sender.phone if sender and sender.phone
                else "Unknown"
            )
            
            # Get metadata from our stored info
            channel_metadata = self.monitored_channels.get(channel_id, {})
            city = channel_metadata.get('city', 'Unknown')
            channel_url = channel_metadata.get('url', 'Unknown')

            # Get channel metadata
            channel_metadata = self.monitored_channels.get(channel_id, {})
            city = channel_metadata.get('city', 'Unknown')
            channel_url = channel_metadata.get('url', 'Unknown')
            channel_name = channel_metadata.get('name', 'Unknown Channel')
            
            # Prepare message data
            message_data = {
                'text': msg.text,
                'date': msg.date.isoformat(),
                'sender': sender_str,
                'channel_name': channel_name,
                'channel_url': channel_url,
                'city': city,
                'message_id': msg.id,
                'channel_id': channel_id
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
            
            # Update offset
            if update_offset:
                self.offset_tracker.update_offset(channel_id, msg.id)
            
        except Exception as e:
            print(f"[ERROR] Error processing message: {e}")

    async def _catchup_missed_messages(self, channel_id: int, entity):
        """
        Fetch and process messages that were missed during downtime.
        """
        last_offset = self.offset_tracker.get_offset(channel_id)
        
        if last_offset is None:
            print(f"[INFO] No previous offset for channel {channel_id}. Skipping catchup.")
            return
        
        print(f"[INFO] Catching up missed messages for channel {channel_id} from message {last_offset}...")
        
        try:
            # Fetch messages newer than last offset
            missed_count = 0
            async for msg in self.client.iter_messages(entity, min_id=last_offset, reverse=True):
                await self._process_message(msg, channel_id, update_offset=False)
                missed_count += 1
            
            if missed_count > 0:
                print(f"[INFO] Processed {missed_count} missed messages for channel {channel_id}.")
                # Update offset to latest after catchup
                self.offset_tracker.update_offset(channel_id, msg.id if missed_count > 0 else last_offset)
            else:
                print(f"[INFO] No missed messages for channel {channel_id}.")
                
        except Exception as e:
            print(f"[ERROR] Error during catchup for channel {channel_id}: {e}")

    async def _run_global_catchup(self):
        """
        Iterates through all monitored channels and reads out any that have been missed.
        Called every time a connection is reconnected.
        """
        print("[INFO] Starting global catch-up for missed messages...")
        
        channel_ids = list(self.monitored_channels.keys())
        
        for channel_id in channel_ids:
            try:
                channel_info = self.monitored_channels.get(channel_id)
                if not channel_info:
                    continue
                
                try:
                    entity = await self.client.get_entity(channel_info['url'])
                except Exception:
                    print(f"[WARN] Could not resolve entity for {channel_info['url']} during catchup")
                    continue

                await self._catchup_missed_messages(channel_id, entity)
                
            except Exception as e:
                print(f"[ERROR] Global catchup failed for channel {channel_id}: {e}")
        
        print("[INFO] Global catch-up completed.")

    async def _handle_new_message(self, event):
        """Handler for real-time new messages."""
        msg = event.message
        chat = await event.get_chat()
        channel_id = chat.id
        
        await self._process_message(msg, channel_id)

    async def _setup_monitoring(self, channels: List[TelegramChannel]):
        """
        Join channels and set up event handlers.
        """
        await self._ensure_connected()
        
        # Join all channels and store metadata
        for channel in channels:
            try:
                success = await self._join_channel(channel.url)
                if not success:
                    continue
                
                entity = await self.client.get_entity(channel.url)
                channel_id = entity.id
                
                self.monitored_channels[channel_id] = {
                    'city': channel.city,
                    'name': channel.name,
                    'url': channel.url
                }
                
                print(f"[INFO] Added {channel.name} ({channel.city}) to monitoring list.")
                
                # Catchup missed messages if not already done
                if channel_id not in self._catchup_done:
                    await self._catchup_missed_messages(channel_id, entity)
                    self._catchup_done.add(channel_id)
                
            except Exception as e:
                print(f"[ERROR] Could not add {channel.url} to monitoring: {e}")
        
        # Set up event handler for new messages
        @self.client.on(events.NewMessage(chats=list(self.monitored_channels.keys())))
        async def message_handler(event):
            try:
                await self._handle_new_message(event)
            except Exception as e:
                print(f"[ERROR] Unhandled exception in event handler: {e}")
        
        print(f"[INFO] Now monitoring {len(self.monitored_channels)} channels for new messages.")

    async def _monitor_with_reconnect(self):
        """
        Main monitoring loop that handles reconnection and catch-up.
        This will run indefinitely until stopped.
        """        
        while not self._stop_event.is_set():
            try:
                await self._ensure_connected()

                await self._run_global_catchup()
                
                print("[INFO] Connection verified. Monitoring...")
                await self.client.run_until_disconnected()
            
            except asyncio.CancelledError:
                break
            except (ConnectionError, OSError, TimeoutError) as e:
                print(f"[WARN] Connection error: {e}")

    async def run(self, container: Container) -> None:
        """
        Start monitoring all channels in the container.
        This runs indefinitely with automatic reconnection.
        """
        channels: List[TelegramChannel] = container.channels
        
        if not channels:
            print("[WARN] No channels to monitor.")
            return
        
        print(f"[INFO] Starting to monitor {len(channels)} channels...")
        
        # Setup monitoring
        await self._setup_monitoring(channels)
        
        if self.use_redis:
            print(f"[INFO] Messages will be sent to Redis queue: {self.redis_queue}")
        print("[INFO] Press Ctrl+C to stop monitoring.\n")
        
        # Start monitoring loop with reconnection
        try:
            await self._monitor_with_reconnect()
        except KeyboardInterrupt:
            print("\n[INFO] Monitoring stopped by user.")

    def stop(self):
        """
        Stop the monitoring service.
        """
        self._stop_event.set()