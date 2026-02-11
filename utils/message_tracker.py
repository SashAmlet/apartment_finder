import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class MessageOffsetTracker:
    """
    Tracks the last processed message ID for each channel.
    Persists to disk to survive restarts.
    """
    
    def __init__(self, storage_path: str = "data/message_offsets.json"):
        self.storage_path = Path(storage_path)
        self.offsets: Dict[int, Dict] = {}  # channel_id -> {last_message_id, last_update}
        self._load()
    
    def _load(self):
        """Load offsets from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to integers
                    self.offsets = {int(k): v for k, v in data.items()}
                print(f"[INFO] Loaded message offsets for {len(self.offsets)} channels.")
            except Exception as e:
                print(f"[WARN] Failed to load offsets: {e}. Starting fresh.")
                self.offsets = {}
        else:
            print("[INFO] No existing offset file found. Starting fresh.")
            self.offsets = {}
    
    def _save(self):
        """Save offsets to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w') as f:
                # Convert integer keys to strings for JSON
                data = {str(k): v for k, v in self.offsets.items()}
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[ERROR] Failed to save offsets: {e}")
    
    def get_offset(self, channel_id: int) -> Optional[int]:
        """Get the last processed message ID for a channel."""
        return self.offsets.get(channel_id, {}).get('last_message_id')
    
    def update_offset(self, channel_id: int, message_id: int):
        """Update the last processed message ID for a channel."""
        self.offsets[channel_id] = {
            'last_message_id': message_id,
            'last_update': datetime.now().isoformat()
        }
        self._save()
    
    def get_all_offsets(self) -> Dict[int, int]:
        """Get all channel offsets as {channel_id: last_message_id}."""
        return {
            channel_id: data['last_message_id']
            for channel_id, data in self.offsets.items()
        }
    
    def clear_offset(self, channel_id: int):
        """Clear the offset for a specific channel."""
        if channel_id in self.offsets:
            del self.offsets[channel_id]
            self._save()
    
    def clear_all(self):
        """Clear all offsets."""
        self.offsets = {}
        self._save()