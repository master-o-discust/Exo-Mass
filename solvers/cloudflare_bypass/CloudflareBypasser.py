import time
import asyncio
from typing import Union, Optional

# Support both DrissionPage and Patchright + Camoufox
try:
    from DrissionPage import ChromiumPage
    DRISSION_AVAILABLE = True
except ImportError:
    ChromiumPage = None
    DRISSION_AVAILABLE = False

try:
    from patchright.async_api import Page as PatchrightPage
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    PatchrightPage = None
    PATCHRIGHT_AVAILABLE = False

class CloudflareBypasser:
    def __init__(self, driver: Union[ChromiumPage, PatchrightPage], max_retries=-1, log=True):
        self.driver = driver
        self.max_retries = max_retries
        self.log = log
        
        # Detect driver type
        self.is_drission = DRISSION_AVAILABLE and isinstance(driver, ChromiumPage)
        self.is_patchright = PATCHRIGHT_AVAILABLE and hasattr(driver, 'query_selector')
        
        if not (self.is_drission or self.is_patchright):
            raise ValueError("Unsupported driver type. Must be DrissionPage ChromiumPage or Patchright Page")

    async def locate_cf_button(self):
        """Locate CloudFlare challenge button - supports both DrissionPage and Patchright"""
        if self.is_drission:
            return self._locate_cf_button_drission()
        elif self.is_patchright:
            return await self._locate_cf_button_patchright()
        return None
    
    def _locate_cf_button_drission(self):
        """DrissionPage implementation for locating CF button"""
        button = None
        eles = self.driver.eles("tag:input")
        for ele in eles:
            if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
                if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
                    try:
                        button = ele.parent().shadow_root.child()("tag:body").shadow_root("tag:input")
                        break
                    except:
                        continue
            
        if button:
            return button
        else:
            # If the button is not found, search it recursively
            self.log_message("Basic search failed. Searching for button recursively.")
            ele = self.driver.ele("tag:body")
            iframe = self._search_recursively_shadow_root_with_iframe_drission(ele)
            if iframe:
                button = self._search_recursively_shadow_root_with_cf_input_drission(iframe("tag:body"))
            else:
                self.log_message("Iframe not found. Button search failed.")
            return button
    
    async def _locate_cf_button_patchright(self):
        """Patchright implementation for locating CF button"""
        try:
            # Look for common CloudFlare challenge selectors
            cf_selectors = [
                'input[name*="turnstile"]',
                'input[name*="cf-turnstile"]',
                'div[class*="cf-turnstile"]',
                'iframe[src*="challenges.cloudflare.com"]',
                'div[class*="challenge"]'
            ]
            
            for selector in cf_selectors:
                elements = await self.driver.query_selector_all(selector)
                if elements:
                    self.log_message(f"Found CF element with selector: {selector}")
                    return elements[0]  # Return first found element
            
            self.log_message("No CF challenge elements found")
            return None
            
        except Exception as e:
            self.log_message(f"Error locating CF button: {e}")
            return None
    
    def _search_recursively_shadow_root_with_iframe_drission(self, ele):
        """DrissionPage recursive shadow root search for iframe"""
        if ele.shadow_root:
            if ele.shadow_root.child().tag == "iframe":
                return ele.shadow_root.child()
        else:
            for child in ele.children():
                result = self._search_recursively_shadow_root_with_iframe_drission(child)
                if result:
                    return result
        return None

    def _search_recursively_shadow_root_with_cf_input_drission(self, ele):
        """DrissionPage recursive shadow root search for CF input"""
        if ele.shadow_root:
            if ele.shadow_root.ele("tag:input"):
                return ele.shadow_root.ele("tag:input")
        else:
            for child in ele.children():
                result = self._search_recursively_shadow_root_with_cf_input_drission(child)
                if result:
                    return result
        return None

    def log_message(self, message):
        if self.log:
            print(message)

    async def click_verification_button(self):
        """Click verification button - supports both DrissionPage and Patchright"""
        try:
            button = await self.locate_cf_button()
            if button:
                self.log_message("Verification button found. Attempting to click.")
                if self.is_drission:
                    button.click()
                elif self.is_patchright:
                    await button.click()
            else:
                self.log_message("Verification button not found.")

        except Exception as e:
            self.log_message(f"Error clicking verification button: {e}")

    async def is_bypassed(self):
        """Check if bypass was successful - supports both DrissionPage and Patchright"""
        try:
            if self.is_drission:
                title = self.driver.title.lower()
            elif self.is_patchright:
                title = (await self.driver.title()).lower()
            else:
                return False
                
            # Check for common CloudFlare challenge indicators
            challenge_indicators = [
                "just a moment",
                "checking your browser",
                "cloudflare",
                "please wait",
                "security check"
            ]
            
            return not any(indicator in title for indicator in challenge_indicators)
            
        except Exception as e:
            self.log_message(f"Error checking page title: {e}")
            return False

    async def bypass(self):
        """Main bypass method - supports both DrissionPage and Patchright"""
        try_count = 0

        while not await self.is_bypassed():
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("Exceeded maximum retries. Bypass failed.")
                break

            self.log_message(f"Attempt {try_count + 1}: Verification page detected. Trying to bypass...")
            
            if self.is_patchright:
                # For Patchright + Camoufox, rely more on built-in anti-detection
                # Just wait and let Camoufox handle the challenge automatically
                self.log_message("Using Camoufox built-in anti-detection features...")
                await asyncio.sleep(5)  # Give more time for automatic bypass
            else:
                # For DrissionPage, try to click the button
                await self.click_verification_button()
                time.sleep(2)

            try_count += 1

        if await self.is_bypassed():
            self.log_message("Bypass successful.")
            return True
        else:
            self.log_message("Bypass failed.")
            return False
