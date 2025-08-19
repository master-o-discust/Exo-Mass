"""
Virtual Display Manager for Turnstile Challenge Solving
Creates and manages Xvfb virtual displays to allow non-headless browser operation
in headless server environments
"""

import os
import subprocess
import logging
import time
import signal
from typing import Optional

logger = logging.getLogger(__name__)

class VirtualDisplayManager:
    """Manages Xvfb virtual displays for browser automation"""
    
    def __init__(self, display_num: int = 99, width: int = 1280, height: int = 720, depth: int = 24):
        self.display_num = display_num
        self.width = width
        self.height = height
        self.depth = depth
        self.display_name = f":{display_num}"
        self.xvfb_process: Optional[subprocess.Popen] = None
        self.original_display = os.environ.get('DISPLAY')
        
    def start_virtual_display(self) -> bool:
        """Start Xvfb virtual display"""
        try:
            logger.info(f"🖥️ Starting virtual display {self.display_name} ({self.width}x{self.height})")
            
            # Check if display is already running
            if self.is_display_running():
                logger.info(f"✅ Virtual display {self.display_name} already running")
                os.environ['DISPLAY'] = self.display_name
                return True
            
            # Start Xvfb
            cmd = [
                'Xvfb',
                self.display_name,
                '-screen', '0', f'{self.width}x{self.height}x{self.depth}',
                '-ac',  # Disable access control
                '-nolisten', 'tcp',  # Don't listen on TCP
                '-dpi', '96',  # Set DPI
                '+extension', 'GLX',  # Enable GLX extension
                '+extension', 'RANDR',  # Enable RANDR extension
            ]
            
            self.xvfb_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Wait for display to start
            time.sleep(2)
            
            if self.is_display_running():
                os.environ['DISPLAY'] = self.display_name
                logger.info(f"✅ Virtual display {self.display_name} started successfully")
                return True
            else:
                logger.error(f"❌ Failed to start virtual display {self.display_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting virtual display: {e}")
            return False
    
    def stop_virtual_display(self) -> bool:
        """Stop Xvfb virtual display"""
        try:
            if self.xvfb_process:
                logger.info(f"🛑 Stopping virtual display {self.display_name}")
                
                # Terminate the process group
                try:
                    os.killpg(os.getpgid(self.xvfb_process.pid), signal.SIGTERM)
                    self.xvfb_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    os.killpg(os.getpgid(self.xvfb_process.pid), signal.SIGKILL)
                    self.xvfb_process.wait()
                
                self.xvfb_process = None
                logger.info(f"✅ Virtual display {self.display_name} stopped")
            
            # Restore original DISPLAY
            if self.original_display:
                os.environ['DISPLAY'] = self.original_display
            elif 'DISPLAY' in os.environ:
                del os.environ['DISPLAY']
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping virtual display: {e}")
            return False
    
    def is_display_running(self) -> bool:
        """Check if the virtual display is running"""
        try:
            # Try to connect to the display
            result = subprocess.run(
                ['xdpyinfo', '-display', self.display_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def __enter__(self):
        """Context manager entry"""
        if self.start_virtual_display():
            return self
        else:
            raise RuntimeError("Failed to start virtual display")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_virtual_display()

# Global instance for easy access
_virtual_display_manager: Optional[VirtualDisplayManager] = None

def get_virtual_display_manager() -> VirtualDisplayManager:
    """Get or create global virtual display manager"""
    global _virtual_display_manager
    if _virtual_display_manager is None:
        _virtual_display_manager = VirtualDisplayManager()
    return _virtual_display_manager

def ensure_virtual_display() -> bool:
    """Ensure virtual display is running"""
    manager = get_virtual_display_manager()
    return manager.start_virtual_display()

def cleanup_virtual_display() -> bool:
    """Cleanup virtual display"""
    global _virtual_display_manager
    if _virtual_display_manager:
        result = _virtual_display_manager.stop_virtual_display()
        _virtual_display_manager = None
        return result
    return True