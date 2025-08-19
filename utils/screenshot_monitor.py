"""
Screenshot Monitor - Takes screenshots every 5 seconds during account checking
"""
import asyncio
import logging
import time
from typing import Optional
from playwright.async_api import Page
from .dropbox_uploader import DropboxUploader

logger = logging.getLogger(__name__)

class ScreenshotMonitor:
    """
    Monitors account checking process and takes screenshots every 5 seconds
    """
    
    def __init__(self, dropbox_uploader: DropboxUploader):
        self.dropbox_uploader = dropbox_uploader
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
    async def start_monitoring(self, page: Page, email: str, process_name: str = "account_check"):
        """
        Start taking screenshots every 5 seconds
        
        Args:
            page: Playwright page to screenshot
            email: Email being checked (for filename)
            process_name: Name of the process (for filename)
        """
        if self.monitoring:
            logger.warning("📸 Screenshot monitoring already running")
            return
            
        self.monitoring = True
        logger.info(f"📸 {email} - Starting screenshot monitoring every 5 seconds...")
        
        # Start the monitoring task
        self.monitor_task = asyncio.create_task(
            self._monitor_loop(page, email, process_name)
        )
        
    async def stop_monitoring(self):
        """Stop screenshot monitoring"""
        if not self.monitoring:
            return
            
        self.monitoring = False
        logger.info("📸 Stopping screenshot monitoring...")
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
                
    async def _monitor_loop(self, page: Page, email: str, process_name: str):
        """
        Main monitoring loop that takes screenshots every 5 seconds
        """
        screenshot_count = 0
        start_time = time.time()
        
        try:
            while self.monitoring:
                try:
                    screenshot_count += 1
                    elapsed_seconds = int(time.time() - start_time)
                    
                    # Create descriptive filename
                    timestamp = int(time.time())
                    safe_email = email.replace('@', '_at_').replace('.', '_')
                    filename = f"{process_name}_{timestamp}_{safe_email}_monitor_{screenshot_count:03d}_{elapsed_seconds}s"
                    
                    # Take screenshot
                    screenshot_bytes = await page.screenshot(full_page=True)
                    
                    # Upload to Dropbox
                    dropbox_path = await self.dropbox_uploader.upload_screenshot(
                        screenshot_bytes, filename
                    )
                    
                    logger.info(f"📸 {email} - Monitor screenshot #{screenshot_count} ({elapsed_seconds}s): {dropbox_path}")
                    
                except Exception as e:
                    logger.error(f"📸 {email} - Error taking monitor screenshot #{screenshot_count}: {e}")
                
                # Wait 5 seconds before next screenshot
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"📸 {email} - Screenshot monitoring cancelled after {screenshot_count} screenshots")
        except Exception as e:
            logger.error(f"📸 {email} - Screenshot monitoring error: {e}")
        finally:
            logger.info(f"📸 {email} - Screenshot monitoring stopped. Total screenshots: {screenshot_count}")