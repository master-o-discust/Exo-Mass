"""
User Agent Manager - Centralized user agent handling using simple-useragent
Replaces all hardcoded user agents with dynamic ones for better stealth
"""
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

class UserAgentManager:
    """Centralized user agent management using simple-useragent package"""
    
    def __init__(self):
        self._sua = None
        self._fallback_desktop = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        self._fallback_mobile = [
            "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ]
        
        # Initialize simple-useragent
        try:
            import simple_useragent as sua
            self._sua = sua
            logger.debug("✅ simple-useragent initialized successfully")
        except ImportError:
            logger.warning("⚠️ simple-useragent not available, using fallback user agents")
    
    def get_desktop_user_agent(self) -> str:
        """Get a random desktop user agent"""
        if self._sua:
            try:
                uas = self._sua.get(desktop=True, shuffle=True)
                if isinstance(uas, list) and uas:
                    ua_obj = random.choice(uas)
                    try:
                        return ua_obj.string
                    except AttributeError:
                        return str(ua_obj)
            except Exception as e:
                logger.warning(f"Error getting desktop user agent from simple-useragent: {e}")
        
        # Fallback to hardcoded list
        return random.choice(self._fallback_desktop)
    
    def get_mobile_user_agent(self, prefer_android: bool = None) -> str:
        """Get a random mobile user agent, optionally preferring Android or iOS"""
        if self._sua:
            try:
                uas = self._sua.get(mobile=True, shuffle=True)
                if isinstance(uas, list) and uas:
                    if prefer_android is True:
                        # Prefer Android
                        android_uas = [ua for ua in uas if 'Android' in str(ua)]
                        if android_uas:
                            ua_obj = random.choice(android_uas)
                        else:
                            ua_obj = random.choice(uas)
                    elif prefer_android is False:
                        # Prefer iOS
                        ios_uas = [ua for ua in uas if any(x in str(ua) for x in ['iPhone', 'iPad', 'iOS'])]
                        if ios_uas:
                            ua_obj = random.choice(ios_uas)
                        else:
                            ua_obj = random.choice(uas)
                    else:
                        # Random mobile
                        ua_obj = random.choice(uas)
                    
                    try:
                        return ua_obj.string
                    except AttributeError:
                        return str(ua_obj)
            except Exception as e:
                logger.warning(f"Error getting mobile user agent from simple-useragent: {e}")
        
        # Fallback to hardcoded list
        if prefer_android is True:
            android_uas = [ua for ua in self._fallback_mobile if 'Android' in ua]
            return random.choice(android_uas) if android_uas else random.choice(self._fallback_mobile)
        elif prefer_android is False:
            ios_uas = [ua for ua in self._fallback_mobile if any(x in ua for x in ['iPhone', 'iPad', 'iOS'])]
            return random.choice(ios_uas) if ios_uas else random.choice(self._fallback_mobile)
        else:
            return random.choice(self._fallback_mobile)
    
    def get_random_user_agent(self) -> str:
        """Get a random mobile user agent (primarily iPhone and Android)"""
        # Prefer mobile user agents for better stealth
        return self.get_mobile_user_agent()
    
    def get_chrome_user_agent(self) -> str:
        """Get a Chrome-specific mobile user agent (Android Chrome or iOS Safari)"""
        if self._sua:
            try:
                uas = self._sua.get(mobile=True, shuffle=True)
                if isinstance(uas, list) and uas:
                    chrome_uas = [ua for ua in uas if 'Chrome' in str(ua) or 'Safari' in str(ua)]
                    if chrome_uas:
                        ua_obj = random.choice(chrome_uas)
                        try:
                            return ua_obj.string
                        except AttributeError:
                            return str(ua_obj)
            except Exception as e:
                logger.warning(f"Error getting Chrome user agent from simple-useragent: {e}")
        
        # Fallback: Chrome-specific mobile from our lists
        chrome_uas = [ua for ua in self._fallback_mobile if 'Chrome' in ua or 'Safari' in ua]
        return random.choice(chrome_uas) if chrome_uas else self._fallback_mobile[0]


# Global instance for easy access
user_agent_manager = UserAgentManager()

# Convenience functions - prioritizing mobile for stealth
def get_desktop_user_agent() -> str:
    """Get a random desktop user agent (use sparingly - mobile preferred)"""
    return user_agent_manager.get_desktop_user_agent()

def get_mobile_user_agent(prefer_android: bool = None) -> str:
    """Get a random mobile user agent (iPhone/Android) - PREFERRED for stealth"""
    return user_agent_manager.get_mobile_user_agent(prefer_android)

def get_random_user_agent() -> str:
    """Get a random mobile user agent (iPhone/Android) - PREFERRED for stealth"""
    return user_agent_manager.get_random_user_agent()

def get_chrome_user_agent() -> str:
    """Get a Chrome-specific mobile user agent (Android Chrome or iOS Safari)"""
    return user_agent_manager.get_chrome_user_agent()

# Primary function - use this for most cases
def get_user_agent() -> str:
    """Get the best user agent for stealth (mobile iPhone/Android)"""
    return user_agent_manager.get_mobile_user_agent()