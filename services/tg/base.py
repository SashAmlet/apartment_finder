import asyncio
from typing import Optional
from abc import ABC

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import (
    UserAlreadyParticipantError,
    InviteHashExpiredError,
    UsernameNotOccupiedError,
    FloodWaitError,
    AuthKeyUnregisteredError,
    PhoneNumberUnoccupiedError
)
from telethon.errors import (
    FloodError,
    RPCError
)

from services.base import Service


MAX_JOIN_ATTEMPTS = 3
MAX_RECONNECT_ATTEMPTS = 10
INITIAL_RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_DELAY = 3000  # 50 minutes


class TelegramServiceBase(Service, ABC):
    """
    Base class for Telegram services with common authentication,
    connection management, and channel joining logic.
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        password: str,
        session_name: str = "telegram_session"
    ):
        super().__init__()
        self.client = TelegramClient(
            session_name, 
            api_id, 
            api_hash, 
            auto_reconnect=False,
            connection_retries=0
            )
        
        self.password = password
        self._is_connected = False
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        
    async def _authenticate(self):
        """
        Authenticate with Telegram.
        Handles 2FA if password is provided.
        """
        if not await self.client.is_user_authorized():
            print("[INFO] Not authorized. Starting authentication...")
            
            try:
                await self.client.start()
                
                # If 2FA is enabled, provide password
                if self.password:
                    try:
                        await self.client.sign_in(password=self.password)
                        print("[INFO] 2FA authentication successful.")
                    except Exception as e:
                        print(f"[WARN] 2FA not needed or already authenticated: {e}")
            except (AuthKeyUnregisteredError, PhoneNumberUnoccupiedError) as e:
                print(f"[ERROR] Authentication failed: {e}")
                raise
        else:
            print("[INFO] Already authorized.")
    
    async def _connect_with_retry(self):
        """
        Connect to Telegram with automatic retry and exponential backoff.
        """
        attempt = 0
        while attempt < MAX_RECONNECT_ATTEMPTS:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                
                await self._authenticate()
                
                self._is_connected = True
                self._reconnect_delay = INITIAL_RECONNECT_DELAY  # Reset delay on success
                print("[INFO] Telegram client connected and authenticated.")
                return True
                
            except (ConnectionError, OSError, TimeoutError) as e:
                attempt += 1
                print(f"[WARN] Connection attempt {attempt}/{MAX_RECONNECT_ATTEMPTS} failed: {e}")
                
                if attempt >= MAX_RECONNECT_ATTEMPTS:
                    print("[ERROR] Max reconnection attempts reached. Giving up.")
                    raise
                
                # Exponential backoff with cap
                wait_time = min(self._reconnect_delay * (2 ** (attempt - 1)), MAX_RECONNECT_DELAY)
                print(f"[INFO] Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                print(f"[ERROR] Unexpected error during connection: {e}")
                raise
        
        return False
    
    async def _ensure_connected(self):
        """
        Ensure the client is connected, reconnect if necessary.
        """
        if not self.client.is_connected():
            print("[WARN] Client disconnected. Reconnecting...")
            await self._connect_with_retry()
    
    async def _join_channel(self, url: str) -> bool:
        """
        Attempt to join a channel/group.
        Returns True if successfully joined or already a member.
        """
        await self._ensure_connected()
        
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
                return True

            except UserAlreadyParticipantError:
                # Not an error - expected behavior
                print(f"[INFO] Already a member of {url}.")
                return True
            
            except (InviteHashExpiredError, UsernameNotOccupiedError) as e:
                print(f"[WARN] Could not join {url}: {e.__class__.__name__}")
                return False

            except FloodWaitError as e:
                wait_time = e.seconds + 1
                print(f"[WARN] Flood wait of {wait_time}s required for {url} on attempt {attempt + 1}/{MAX_JOIN_ATTEMPTS}.")
                await asyncio.sleep(wait_time)

            except (ConnectionError, OSError) as e:
                print(f"[WARN] Connection error while joining {url}: {e}")
                await self._ensure_connected()
                await asyncio.sleep(5)

            except Exception as e:
                print(f"[ERROR] Unexpected error when trying to join {url}: {e}")
                await asyncio.sleep(5)
        
        print(f"[ERROR] Failed to join {url} after {MAX_JOIN_ATTEMPTS} attempts.")
        return False
    
    async def __aenter__(self):
        """
        Context manager entry - connect and authenticate.
        """
        await self._connect_with_retry()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - disconnect client.
        """
        if self.client.is_connected():
            await self.client.disconnect()
            print("[INFO] Telegram client disconnected.")
        self._is_connected = False