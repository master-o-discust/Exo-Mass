"""
CloudFlare Solver - BotsForge implementation
Based on BotsForge/CloudFlare repository
"""

try:
    from .browser import Browser as CloudflareBrowser, PYAUTOGUI_AVAILABLE
    from .models import CaptchaTask
    BOTSFORGE_AVAILABLE = True
    # Note: BotsForge uses Patchright (same as main system) but manages its own browser instances
except ImportError as e:
    BOTSFORGE_AVAILABLE = False
    CloudflareBrowser = None
    CaptchaTask = None
    PYAUTOGUI_AVAILABLE = False

__all__ = ['CloudflareBrowser', 'CaptchaTask', 'BOTSFORGE_AVAILABLE', 'PYAUTOGUI_AVAILABLE']