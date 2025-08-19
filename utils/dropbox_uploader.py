import aiohttp
import asyncio
import base64
import json
import logging
import time
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class DropboxTokenManager:
    _access_token: Optional[str] = None
    _expires_at: float = 0.0
    _last_refresh: float = 0.0
    _lock = asyncio.Lock()
    
    # Refresh token every 3 hours (10800 seconds)
    REFRESH_INTERVAL = 3 * 60 * 60  # 3 hours in seconds

    @classmethod
    async def get_access_token(cls) -> Optional[str]:
        """Get a valid Dropbox access token, refreshing if necessary"""
        if not settings.DROPBOX_ENABLED:
            logger.debug("Dropbox is disabled")
            return None
        
        if not (settings.DROPBOX_APP_KEY and settings.DROPBOX_APP_SECRET and settings.DROPBOX_REFRESH_TOKEN):
            logger.error("Dropbox credentials not configured properly")
            return None

        async with cls._lock:
            current_time = time.time()
            
            # Check if we need to refresh (every 3 hours or if token is expired/missing)
            needs_refresh = (
                not cls._access_token or 
                current_time >= cls._expires_at - 60 or  # 1 minute before expiry
                current_time >= cls._last_refresh + cls.REFRESH_INTERVAL  # Every 3 hours
            )
            
            if not needs_refresh:
                return cls._access_token

            return await cls._refresh_token()

    @classmethod
    async def force_refresh(cls) -> Optional[str]:
        """Force refresh the Dropbox access token"""
        if not settings.DROPBOX_ENABLED:
            logger.debug("Dropbox is disabled")
            return None
        
        if not (settings.DROPBOX_APP_KEY and settings.DROPBOX_APP_SECRET and settings.DROPBOX_REFRESH_TOKEN):
            logger.error("Dropbox credentials not configured properly")
            return None

        async with cls._lock:
            return await cls._refresh_token()

    @classmethod
    async def _refresh_token(cls) -> Optional[str]:
        """Internal method to refresh the token"""
        logger.info("Refreshing Dropbox access token...")
        
        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": settings.DROPBOX_REFRESH_TOKEN,
        }

        # Create Basic Auth header
        auth_string = f"{settings.DROPBOX_APP_KEY}:{settings.DROPBOX_APP_SECRET}"
        auth_basic = base64.b64encode(auth_string.encode()).decode()

        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(token_url, data=data, headers={
                    "Authorization": f"Basic {auth_basic}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Dropbox token refresh failed: {resp.status} - {text[:500]}")
                        return None
                    
                    payload = await resp.json()
                    cls._access_token = payload.get("access_token")
                    expires_in = payload.get("expires_in", 14400)  # default 4 hours
                    cls._expires_at = time.time() + float(expires_in)
                    cls._last_refresh = time.time()
                    
                    if cls._access_token:
                        logger.info(f"Dropbox access token refreshed successfully (expires in {expires_in/3600:.1f} hours)")
                    else:
                        logger.error("No access token in response")
                    
                    return cls._access_token
        except Exception as e:
            logger.error(f"Error refreshing Dropbox token: {e}")
            return None

class DropboxUploader:
    @staticmethod
    async def ensure_folder(access_token: str, path: str) -> bool:
        """Create folder in Dropbox if it doesn't exist"""
        if not path or path == "/":
            return True
            
        # Normalize path
        path = path.strip("/")
        if not path:
            return True
        path = "/" + path
        
        api_url = "https://api.dropboxapi.com/2/files/create_folder_v2"
        timeout = aiohttp.ClientTimeout(total=30)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {"path": path, "autorename": False}
                async with session.post(api_url, json=payload, headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }) as resp:
                    if resp.status == 200:
                        logger.info(f"Dropbox folder created: {path}")
                        return True
                    elif resp.status == 409:
                        # 409 conflict means folder already exists
                        logger.debug(f"Dropbox folder already exists: {path}")
                        return True
                    else:
                        text = await resp.text()
                        logger.warning(f"Dropbox folder creation failed for {path}: {resp.status} - {text[:300]}")
                        return False
        except Exception as e:
            logger.error(f"Error creating Dropbox folder {path}: {e}")
            return False
    
    @staticmethod
    async def ensure_folder_recursive(access_token: str, path: str) -> bool:
        """Create folder and all parent folders recursively"""
        if not path or path == "/":
            return True
            
        # Normalize path
        path = path.strip("/")
        if not path:
            return True
        
        # Split path into parts and create each level
        parts = path.split("/")
        current_path = ""
        
        for part in parts:
            if part:  # Skip empty parts
                current_path += "/" + part
                if not await DropboxUploader.ensure_folder(access_token, current_path):
                    # If creation fails but it's not because folder exists, return False
                    # We'll check if folder exists by trying to list it
                    try:
                        list_url = "https://api.dropboxapi.com/2/files/list_folder"
                        timeout = aiohttp.ClientTimeout(total=30)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            payload = {"path": current_path}
                            async with session.post(list_url, json=payload, headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json"
                            }) as resp:
                                if resp.status != 200:
                                    logger.error(f"Failed to create or verify folder: {current_path}")
                                    return False
                    except Exception as e:
                        logger.error(f"Error verifying folder {current_path}: {e}")
                        return False
        
        return True

    @staticmethod
    async def upload_file(local_path: str, dropbox_path: str) -> bool:
        """Upload a file to Dropbox at the specified path. Returns True on success."""
        if not settings.DROPBOX_ENABLED:
            logger.debug("Dropbox upload skipped - disabled")
            return False
            
        token = await DropboxTokenManager.get_access_token()
        if not token:
            logger.error("No Dropbox access token available")
            return False

        # Ensure parent folder exists
        parent_folder = "/".join(dropbox_path.split("/")[:-1])
        if parent_folder and parent_folder != "/":
            if not await DropboxUploader.ensure_folder_recursive(token, parent_folder):
                logger.error(f"Failed to create parent folder: {parent_folder}")
                return False

        # Read file data
        try:
            with open(local_path, "rb") as f:
                data = f.read()
        except Exception as e:
            logger.error(f"Error reading file {local_path}: {e}")
            return False

        # Upload file
        content_url = "https://content.dropboxapi.com/2/files/upload"
        timeout = aiohttp.ClientTimeout(total=180)  # Increased timeout for large files
        
        args = {
            "path": dropbox_path,
            "mode": {".tag": "overwrite"},
            "autorename": False,
            "mute": True,
            "strict_conflict": False
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(content_url, data=data, headers={
                    "Authorization": f"Bearer {token}",
                    "Dropbox-API-Arg": json.dumps(args),
                    "Content-Type": "application/octet-stream"
                }) as resp:
                    if resp.status == 200:
                        logger.info(f"File uploaded to Dropbox: {dropbox_path}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"Dropbox upload failed for {dropbox_path}: {resp.status} - {text[:300]}")
                        return False
        except Exception as e:
            logger.error(f"Error uploading file to Dropbox: {e}")
            return False

    @staticmethod
    async def upload_screenshot(screenshot_bytes: bytes, filename: str) -> Optional[str]:
        """Upload screenshot bytes to Dropbox. Returns Dropbox path on success."""
        if not settings.DROPBOX_ENABLED:
            logger.debug("Dropbox screenshot upload skipped - disabled")
            return None
        
        token = await DropboxTokenManager.get_access_token()
        if not token:
            logger.error("No Dropbox access token available for screenshot upload")
            return None

        # Create path for screenshots with date folder structure
        from datetime import datetime
        date_folder = datetime.now().strftime("%Y-%m-%d")
        dropbox_path = DropboxUploader.build_dropbox_path("screenshots", date_folder, filename)
        
        # Ensure parent folder exists recursively
        parent_folder = "/".join(dropbox_path.split("/")[:-1])
        if parent_folder and parent_folder != "/":
            if not await DropboxUploader.ensure_folder_recursive(token, parent_folder):
                logger.error(f"Failed to create screenshot folder: {parent_folder}")
                return None

        # Upload screenshot bytes
        content_url = "https://content.dropboxapi.com/2/files/upload"
        timeout = aiohttp.ClientTimeout(total=120)

        args = {
            "path": dropbox_path,
            "mode": {".tag": "overwrite"},
            "autorename": True,  # Auto-rename if file exists
            "mute": True,
            "strict_conflict": False
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(content_url, data=screenshot_bytes, headers={
                    "Authorization": f"Bearer {token}",
                    "Dropbox-API-Arg": json.dumps(args),
                    "Content-Type": "application/octet-stream"
                }) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                        actual_path = response_data.get("path_display", dropbox_path)
                        logger.info(f"Screenshot uploaded to Dropbox: {actual_path}")
                        return actual_path
                    else:
                        text = await resp.text()
                        logger.error(f"Dropbox screenshot upload failed: {resp.status} - {text[:300]}")
                        return None
        except Exception as e:
            logger.error(f"Error uploading screenshot to Dropbox: {e}")
            return None

    @staticmethod
    def build_dropbox_path(*parts: str) -> str:
        base = settings.DROPBOX_BASE_FOLDER.strip("/") or "ExoMassChecker"
        path = "/" + "/".join([base] + [p.strip("/") for p in parts if p])
        return path
