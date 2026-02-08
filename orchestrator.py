import asyncio
from datetime import datetime
import json
import redis
import copy
from typing import Dict, List, Optional

from models import Container, TelegramChannel, TelegramMessage

from service_factory import ServiceFactory
from session_manager import SessionManager

from models import Container

class Orchestrator:
    """
    Управляет выполнением пайплайна сервисов на основе конфигурационного файла.
    Поддерживает опциональное переиспользование артефактов (кэша)
    из предыдущих запусков (сессий).
    """
    def __init__(self, config: Dict, session_manager: SessionManager):
        """
        Инициализируется конфигурацией пайплайна и менеджером сессий.
        """
        self.pipeline_config = config.get('pipeline', [])
        self.run_config = config.get('run_config', {})
        self.redis_config = config.get('redis', {})
        self.batch_config = config.get('batch_processing', {})
        
        self.redis_client: Optional[redis.Redis] = None
        self._stop_monitoring = asyncio.Event()
        self.session_manager = session_manager
        self.service_factory = ServiceFactory()
        print("[INFO] Orchestrator is initialized with config-driven pipeline.")

    async def run(self, initial_input: Container) -> None:
        """
        Выполняет пайплайн, определенный в конфигурационном файле.
        """
        current_data = initial_input
        
        source_session_id = self.run_config.get('source_session_id', 'none')
        source_session_path = self.session_manager.find_session_path(source_session_id)

        if source_session_path:
            print(f"[INFO] Using source session for cache: {source_session_path}")
        else:
            print(f"[WARN] Source session '{source_session_id}' not found. Cache will not be used.")

        for step_config in self.pipeline_config:
            service_name = step_config['service']
            params = step_config.get('params', {})
            use_cache = step_config.get('use_cache', False)
            
            cached_data = None
            if use_cache and source_session_path:
                print(f"[INFO] Attempting to load cached snapshot for '{service_name}'...")
                cached_data = await self.session_manager.load_snapshot(source_session_path, service_name)

            if cached_data:
                print(f"[INFO] >>> Cache HIT for '{service_name}'. Skipping execution.")
                current_data = cached_data
            else:
                if use_cache:
                    print(f"[INFO] >>> Cache MISS for '{service_name}'. Running service.")
                
                # Создаем сервис с параметрами из конфига
                service = await self.service_factory.create_service(
                    name=service_name, 
                    params=params
                )

                # Запускаем реальную логику сервиса
                if hasattr(service, "__aenter__") and hasattr(service, "__aexit__"):    
                    print(f"[INFO] Orchestrator is running '{service_name}' within context...")
                    async with service:
                        current_data = await service.run(current_data)
                    
                else:
                    # Сервис не требует управления жизненным циклом
                    print(f"[INFO] Orchestrator is running '{service_name}'...")
                    current_data = await service.run(current_data)
            
            # Сохраняем результат (новый или из кэша) как артефакт ТЕКУЩЕЙ сессии
            await self.session_manager.save_snapshot(service_name, copy.deepcopy(current_data))

        print("\n[INFO] Pipeline finished successfully.")
        print(f"[INFO] All artifacts for this run are saved in: {self.session_manager.session_path}")

    async def _get_redis_client(self) -> redis.Redis:
        """
        Создает или возвращает существующее подключение к Redis.
        """
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=self.redis_config['host'],
                port=self.redis_config['port'],
                db=self.redis_config['db'],
                decode_responses=True
            )
            print(f"[INFO] Connected to Redis at {self.redis_config['host']}:{self.redis_config['port']}")
        return self.redis_client

    async def _close_redis_client(self):
        """
        Закрывает соединение с Redis.
        """
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            print("[INFO] Redis connection closed.")

    async def _collect_messages_from_redis(self, redis_client: redis.Redis, count: int) -> List[Dict]:
        """
        Извлекает count сообщений из Redis очереди.
        """
        queue_name = self.redis_config['queue_name']
        messages = []
        
        for _ in range(count):
            # Pop message from the queue (LPOP removes from the left/head)
            message_str = await redis_client.lpop(queue_name)
            if message_str is None:
                break
            
            try:
                message_data = json.loads(message_str)
                messages.append(message_data)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to decode message from Redis: {e}")
                continue
        
        return messages

    async def _messages_to_container(self, messages: List[Dict]) -> Container:
        """
        Преобразует список сообщений из Redis в Container с TelegramChannel.
        
        Группирует сообщения по каналам.
        """
        # Group messages by channel
        channels_dict = {}
        
        for msg_data in messages:
            channel_url = msg_data.get('channel_url', 'unknown')
            channel_name = msg_data.get('channel_name', 'Unknown Channel')
            city = msg_data.get('city', 'Unknown')
            
            if channel_url not in channels_dict:
                channels_dict[channel_url] = TelegramChannel(
                    city=city,
                    name=channel_name,
                    url=channel_url,
                    messages=[]
                )
            
            # Create TelegramMessage
            telegram_msg = TelegramMessage(
                text=msg_data.get('text', ''),
                date=datetime.fromisoformat(msg_data.get('date')) if msg_data.get('date') else datetime.now(),
                sender=msg_data.get('sender', 'Unknown')
            )
            
            channels_dict[channel_url].messages.append(telegram_msg)
        
        return Container(channels=list(channels_dict.values()))

    async def monitor_redis_and_process(self):
        """
        Непрерывно мониторит Redis очередь и запускает пайплайн когда:
        - Накопилось X сообщений, ИЛИ
        - Прошло Y минут с последней обработки
        """
        redis_client = await self._get_redis_client()
        queue_name = self.redis_config['queue_name']
        
        max_messages = self.batch_config['max_messages']
        max_wait_minutes = self.batch_config['max_wait_minutes']
        
        last_process_time = datetime.now()
        check_interval = 10  # Check every 10 seconds
        
        print(f"[INFO] Starting Redis queue monitoring...")
        print(f"[INFO] Batch triggers: {max_messages} messages OR {max_wait_minutes} minutes")
        print(f"[INFO] Queue name: {queue_name}\n")
        
        try:
            while not self._stop_monitoring.is_set():
                # Get current queue length
                queue_length = await redis_client.llen(queue_name)
                time_elapsed = (datetime.now() - last_process_time).total_seconds() / 60
                
                should_process = False
                reason = ""
                
                # Check if we should process
                if queue_length >= max_messages:
                    should_process = True
                    reason = f"message count threshold reached ({queue_length}/{max_messages})"
                elif time_elapsed >= max_wait_minutes and queue_length > 0:
                    should_process = True
                    reason = f"time threshold reached ({time_elapsed:.1f}/{max_wait_minutes} min) with {queue_length} messages"
                
                if should_process:
                    print(f"\n{'='*70}")
                    print(f"[TRIGGER] Processing batch: {reason}")
                    print(f"{'='*70}\n")
                    
                    # Collect all messages from queue
                    messages = await self._collect_messages_from_redis(redis_client, queue_length)
                    
                    if messages:
                        print(f"[INFO] Collected {len(messages)} messages from Redis queue.")
                        
                        # Convert to Container
                        container: Container = await self._messages_to_container(messages)
                        
                        print(f"[INFO] Created Container with {len(container.channels)} channels.")
                        
                        # Run the full pipeline using existing run() method
                        await self.run(container)
                        
                        print(f"[INFO] Batch processing completed successfully.")
                    
                    # Reset timer
                    last_process_time = datetime.now()
                else:
                    # Log status periodically
                    if int(time_elapsed * 60) % 60 == 0:  # Every minute
                        print(f"[STATUS] Queue: {queue_length} messages | Time elapsed: {time_elapsed:.1f}/{max_wait_minutes} min")
                
                # Wait before next check
                await asyncio.sleep(check_interval)
        
        except asyncio.CancelledError:
            print("\n[INFO] Redis monitoring cancelled.")
        except Exception as e:
            print(f"\n[ERROR] Error in Redis monitoring: {e}")
        finally:
            await self._close_redis_client()

    def stop_monitoring(self):
        """
        Останавливает мониторинг Redis очереди.
        """
        print("[INFO] Stopping Redis monitoring...")
        self._stop_monitoring.set()