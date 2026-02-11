import asyncio
import json
from pathlib import Path
from orchestrator import Orchestrator
from session_manager import SessionManager
from models import Container

from utils.utils import load_channels


async def main():
    """
    Run TgMonitorService to continuously watch channels and send messages to Redis.
    Uses Orchestrator to manage the service lifecycle.
    """
    # Load monitoring configuration
    with open('data/configs/config-monitor-tg.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Load channels from snapshot
    try:
        snapshot_path = config.get('channels_snapshot_path', 'data/SessionResults/2025-12-23_23-45-59/WebFilterService_snapshot.json')
        initial_data = await load_channels(snapshot_path)
    except FileNotFoundError as e:
        print(f"[WARN] {e}")
        print("[WARN] Starting with an empty container.")
        initial_data = Container(channels=[])
    
    if not initial_data.channels:
        print("[ERROR] No channels to monitor. Exiting.")
        return
    
    # Initialize SessionManager
    session_manager = SessionManager()
    
    # Create and run Orchestrator
    orchestrator = Orchestrator(config, session_manager)
    
    print("\n" + "="*70)
    print("TELEGRAM MONITOR SERVICE")
    print("="*70)
    print(f"Channels to monitor: {len(initial_data.channels)}")
    redis_config = config.get('redis', {})
    print(f"Redis enabled: {redis_config.get('enabled', True)}")
    print(f"Redis queue: {redis_config.get('queue_name', 'telegram_messages')}")
    print("="*70)
    print("[INFO] Starting Telegram monitoring service via Orchestrator...")
    print("[INFO] Press Ctrl+C to stop.\n")
    
    try:
        await orchestrator.run(initial_data)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping monitor...")
    finally:
        print("[INFO] Monitor stopped.")


if __name__ == "__main__":
    asyncio.run(main())