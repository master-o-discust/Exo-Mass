"""
Display Detection Utility
Detects if a visual display is available and configures browser accordingly
"""
import os
import platform
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class DisplayDetector:
    """Detects display availability and provides appropriate configuration"""
    
    def __init__(self):
        self._display_available = None
        self._screen_size = None
        self._is_headless_environment = None
    
    def has_display(self) -> bool:
        """Check if a visual display is available"""
        if self._display_available is not None:
            return self._display_available
        
        try:
            system = platform.system()
            
            if system == "Linux":
                # Check for DISPLAY environment variable
                if 'DISPLAY' not in os.environ:
                    logger.info("🖥️ No DISPLAY environment variable found")
                    self._display_available = False
                    return False
                
                # Try to connect to X server
                try:
                    import subprocess
                    result = subprocess.run(['xset', 'q'], 
                                          capture_output=True, 
                                          timeout=5)
                    if result.returncode == 0:
                        logger.info("🖥️ X11 display available")
                        self._display_available = True
                        return True
                    else:
                        logger.info("🖥️ X11 display not accessible")
                        self._display_available = False
                        return False
                except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                    logger.info(f"🖥️ Cannot check X11 display: {e}")
                    self._display_available = False
                    return False
            
            elif system == "Windows":
                # On Windows, assume display is available unless explicitly headless
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    screen_width = user32.GetSystemMetrics(0)
                    screen_height = user32.GetSystemMetrics(1)
                    
                    if screen_width > 0 and screen_height > 0:
                        logger.info(f"🖥️ Windows display available: {screen_width}x{screen_height}")
                        self._display_available = True
                        return True
                    else:
                        logger.info("🖥️ Windows display not available")
                        self._display_available = False
                        return False
                except Exception as e:
                    logger.warning(f"🖥️ Error checking Windows display: {e}")
                    self._display_available = False
                    return False
            
            elif system == "Darwin":  # macOS
                # On macOS, assume display is available unless explicitly headless
                try:
                    import subprocess
                    result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                          capture_output=True, 
                                          timeout=10)
                    if result.returncode == 0 and b'Resolution' in result.stdout:
                        logger.info("🖥️ macOS display available")
                        self._display_available = True
                        return True
                    else:
                        logger.info("🖥️ macOS display not available")
                        self._display_available = False
                        return False
                except Exception as e:
                    logger.warning(f"🖥️ Error checking macOS display: {e}")
                    self._display_available = False
                    return False
            
            else:
                logger.info(f"🖥️ Unknown system: {system}, assuming no display")
                self._display_available = False
                return False
                
        except Exception as e:
            logger.error(f"❌ Error detecting display: {e}")
            self._display_available = False
            return False
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen size if display is available"""
        if self._screen_size is not None:
            return self._screen_size
        
        if not self.has_display():
            # Return default size for headless mode
            self._screen_size = (1920, 1080)
            return self._screen_size
        
        try:
            system = platform.system()
            
            if system == "Windows":
                import ctypes
                user32 = ctypes.windll.user32
                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)
                self._screen_size = (width, height)
                
            elif system == "Linux":
                try:
                    import subprocess
                    result = subprocess.run(['xrandr'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if '*' in line and 'x' in line:
                                # Parse resolution like "1920x1080"
                                parts = line.strip().split()
                                for part in parts:
                                    if 'x' in part and part.replace('x', '').replace('.', '').isdigit():
                                        width, height = map(int, part.split('x'))
                                        self._screen_size = (width, height)
                                        break
                                break
                except Exception:
                    pass
                
                if self._screen_size is None:
                    self._screen_size = (1920, 1080)  # Default
                    
            elif system == "Darwin":  # macOS
                try:
                    import subprocess
                    result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'Resolution:' in line:
                                # Parse resolution like "Resolution: 1920 x 1080"
                                parts = line.split(':')[1].strip().split('x')
                                if len(parts) == 2:
                                    width = int(parts[0].strip())
                                    height = int(parts[1].strip())
                                    self._screen_size = (width, height)
                                    break
                except Exception:
                    pass
                
                if self._screen_size is None:
                    self._screen_size = (1920, 1080)  # Default
            
            else:
                self._screen_size = (1920, 1080)  # Default for unknown systems
            
            logger.info(f"🖥️ Screen size: {self._screen_size[0]}x{self._screen_size[1]}")
            return self._screen_size
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting screen size: {e}")
            self._screen_size = (1920, 1080)  # Default fallback
            return self._screen_size
    
    def is_headless_environment(self) -> bool:
        """Check if we're running in a headless environment (server, container, etc.)"""
        if self._is_headless_environment is not None:
            return self._is_headless_environment
        
        # Check common headless environment indicators
        headless_indicators = [
            not self.has_display(),
            os.environ.get('CI') == 'true',  # CI/CD environments
            os.environ.get('GITHUB_ACTIONS') == 'true',  # GitHub Actions
            os.environ.get('DOCKER_CONTAINER') == 'true',  # Docker
            os.path.exists('/.dockerenv'),  # Docker container
            os.environ.get('SSH_CONNECTION') is not None,  # SSH session
            os.environ.get('TERM') == 'dumb',  # Non-interactive terminal
        ]
        
        self._is_headless_environment = any(headless_indicators)
        
        if self._is_headless_environment:
            logger.info("🖥️ Detected headless environment")
        else:
            logger.info("🖥️ Detected interactive environment with display")
        
        return self._is_headless_environment
    
    def get_browser_config(self) -> dict:
        """Get appropriate browser configuration based on display availability"""
        has_display = self.has_display()
        is_headless = self.is_headless_environment()
        
        config = {
            'headless': is_headless or not has_display,
            'has_display': has_display,
            'screen_size': self.get_screen_size(),
            'can_use_pyautogui': has_display and not is_headless,
            'can_position_windows': has_display and not is_headless
        }
        
        logger.info(f"🖥️ Browser config: headless={config['headless']}, "
                   f"display={config['has_display']}, "
                   f"pyautogui={config['can_use_pyautogui']}")
        
        return config


# Global instance
display_detector = DisplayDetector()

def get_display_detector() -> DisplayDetector:
    """Get the global display detector instance"""
    return display_detector

def has_display() -> bool:
    """Quick check if display is available"""
    return display_detector.has_display()

def get_browser_config() -> dict:
    """Quick access to browser configuration"""
    return display_detector.get_browser_config()