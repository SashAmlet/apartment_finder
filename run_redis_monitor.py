import asyncio
import json
from orchestrator import Orchestrator
from session_manager import SessionManager


async def main():
    """
    Monitor Redis queue and process batches through the pipeline.
    
    This script watches the Redis queue for messages from TgMonitorService.
    When the batch threshold is reached (by count or time), it:
    1. Collects messages from Redis
    2. Creates a Container
    3. Runs the pipeline starting from TgFilterService
    4. Results get published by TgPublisherService
    """
    # Load config
    try:
        with open('data\\configs\\config-monitor-redis.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("[ERROR] config-monitor-redis.json not found! Please create a configuration file.")
        return
    except json.JSONDecodeError:
        print("[ERROR] Could not parse config-monitor-redis.json. Please check for syntax errors.")
        return
    
    # Initialize session manager
    session_manager = SessionManager()
    
    # Create orchestrator
    orchestrator = Orchestrator(config, session_manager)
    
    batch_config = config.get('batch_processing', {})
    max_messages = batch_config.get('max_messages', 100)
    max_wait_minutes = batch_config.get('max_wait_minutes', 5)
    
    print("="*70)
    print("REDIS BATCH PROCESSOR")
    print("="*70)
    print(f"Queue: {config.get('redis', {}).get('queue_name', 'telegram_messages')}")
    print(f"Batch triggers: {max_messages} messages OR {max_wait_minutes} minutes")
    print(f"Pipeline: Full pipeline as defined in config.json")
    print("="*70)
    print("\n[INFO] Starting Redis queue monitoring...")
    print("[INFO] Press Ctrl+C to stop.\n")
    
    try:
        # Start monitoring (this will run indefinitely)
        await orchestrator.monitor_redis_and_process()
    
    except KeyboardInterrupt:
        print("\n[INFO] Stopping...")
        orchestrator.stop_monitoring()
    
    finally:
        print("[INFO] Cleanup complete.")


if __name__ == "__main__":
    asyncio.run(main())