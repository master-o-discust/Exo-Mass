"""
Unified Turnstile Handler - Integrates all three solver methods
1. Primary: Turnstile Solver (Theyka/Turnstile-Solver)
2. Fallback 1: CloudFlare BotsForge (BotsForge/CloudFlare)
3. Fallback 2: CloudFlare Bypass (sarperavci/CloudflareBypassForScraping)

Features:
- Uses user-uploaded proxies from Telegram menus
- Uses user agents from simple_useragent package (no hardcoded UAs)
- Maintains session cookies and user agents across URL navigations
- Takes screenshots on successful login and uploads to Dropbox
- Proper fallback chain with error handling
"""

import asyncio
import logging
import time
import aiohttp
import base64
import re
import os
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
try:
    from patchright.async_api import Page
except ImportError:
    from playwright.async_api import Page

# Import solver manager for DrissionPage bypasser only
from utils.solver_manager import get_solver_manager

# Import utilities
from utils.dropbox_uploader import DropboxUploader

# Optional DrissionPage and CF bypass imports (guarded)
try:
    from DrissionPage import ChromiumPage, ChromiumOptions
except Exception:
    ChromiumPage = None
    ChromiumOptions = None
try:
    from solvers.cloudflare_bypass import CloudflareBypasser
except Exception:
    CloudflareBypasser = None
from config.settings import (
    ENABLE_TURNSTILE_SERVICE,
    TURNSTILE_SERVICE_HOST,
    TURNSTILE_SERVICE_PORT,
    TURNSTILE_TIMEOUT,
    BOTSFORGE_SERVICE_HOST,
    BOTSFORGE_SERVICE_PORT,
    BOTSFORGE_API_KEY,
    ENABLE_BOTSFORGE_SERVICE,
    DEBUG_ENHANCED_FEATURES,
    DROPBOX_ENABLED
)

logger = logging.getLogger(__name__)

async def detect_turnstile_challenge(page: Page, max_wait_time: int = 30) -> Dict[str, Any]:
    """
    Enhanced Turnstile challenge detection with proper waiting and sitekey extraction
    Based on best practices from 2captcha and professional CAPTCHA solving tools
    """
    logger.info("🔍 Starting enhanced Turnstile challenge detection...")
    
    # Primary detection patterns (most reliable)
    primary_patterns = [
        # Cloudflare Turnstile (most common)
        {'selector': 'div[data-sitekey]', 'type': 'Cloudflare Turnstile'},
        {'selector': '#cf-turnstile', 'type': 'Cloudflare Turnstile'},
        {'selector': '.cf-turnstile', 'type': 'Cloudflare Turnstile'},
        {'selector': '[data-sitekey*="0x"]', 'type': 'Cloudflare Turnstile'},
        
        # Generic Turnstile patterns
        {'selector': '.turnstile-wrapper', 'type': 'Turnstile Wrapper'},
        {'selector': '[class*="turnstile"]', 'type': 'Generic Turnstile'},
        {'selector': '[id*="turnstile"]', 'type': 'Generic Turnstile'},
    ]
    
    # Extended patterns for deeper search
    extended_patterns = [
        {'selector': 'iframe[src*="challenges.cloudflare.com"]', 'type': 'Cloudflare Challenge'},
        {'selector': 'iframe[src*="turnstile"]', 'type': 'Turnstile iframe'},
        {'selector': '[data-cf-turnstile-sitekey]', 'type': 'CF Turnstile Alt'},
        {'selector': '[data-turnstile-sitekey]', 'type': 'Turnstile Alt'},
        {'selector': 'form [data-sitekey]', 'type': 'Form Turnstile'},
        {'selector': '[class*="challenge"]', 'type': 'Challenge Element'},
    ]
    
    start_time = time.time()
    challenge_info = None
    
    # Phase 1: Quick initial check
    if DEBUG_ENHANCED_FEATURES:
        logger.info("🔍 Phase 1: Quick initial detection...")
    
    challenge_info = await _check_turnstile_patterns(page, primary_patterns)
    if challenge_info:
        logger.info(f"✅ Found Turnstile challenge immediately: {challenge_info['type']}")
        return challenge_info
    
    # Phase 2: Wait for dynamic content with periodic checks
    if DEBUG_ENHANCED_FEATURES:
        logger.info("🔍 Phase 2: Waiting for dynamic Turnstile content...")
    
    check_interval = 2  # Check every 2 seconds
    checks_performed = 0
    
    while time.time() - start_time < max_wait_time:
        await asyncio.sleep(check_interval)
        checks_performed += 1
        
        if DEBUG_ENHANCED_FEATURES and checks_performed % 3 == 0:  # Log every 6 seconds
            elapsed = int(time.time() - start_time)
            logger.info(f"🔄 Still searching for Turnstile... ({elapsed}s elapsed)")
        
        # Check primary patterns first
        challenge_info = await _check_turnstile_patterns(page, primary_patterns)
        if challenge_info:
            logger.info(f"✅ Found Turnstile challenge after {int(time.time() - start_time)}s: {challenge_info['type']}")
            return challenge_info
        
        # After 10 seconds, also check extended patterns
        if time.time() - start_time > 10:
            challenge_info = await _check_turnstile_patterns(page, extended_patterns)
            if challenge_info:
                logger.info(f"✅ Found Turnstile challenge (extended) after {int(time.time() - start_time)}s: {challenge_info['type']}")
                return challenge_info
    
    # Phase 3: Final comprehensive check
    if DEBUG_ENHANCED_FEATURES:
        logger.info("🔍 Phase 3: Final comprehensive check...")
    
    all_patterns = primary_patterns + extended_patterns
    challenge_info = await _check_turnstile_patterns(page, all_patterns)
    
    if challenge_info:
        logger.info(f"✅ Found Turnstile challenge in final check: {challenge_info['type']}")
        return challenge_info
    
    # Phase 4: Check for response inputs (indicates Turnstile was present)
    try:
        response_inputs = await page.query_selector_all('input[name*="turnstile"], input[name*="cf-turnstile-response"]')
        if response_inputs:
            logger.info("🎯 Found Turnstile response inputs - challenge may have been solved automatically")
            return {
                'detected': True,
                'type': 'Turnstile Response Found',
                'sitekey': None,
                'url': page.url,
                'selector': 'input[name*="turnstile"]',
                'auto_solved': True
            }
    except Exception as e:
        logger.debug(f"Error checking response inputs: {e}")
    
    logger.warning(f"❌ No Turnstile challenge detected after {max_wait_time}s search")
    return {
        'detected': False,
        'type': 'No Challenge',
        'sitekey': None,
        'url': page.url,
        'selector': None,
        'auto_solved': False
    }

async def _check_turnstile_patterns(page: Page, patterns: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Check a list of Turnstile patterns and return the first match found"""
    for pattern in patterns:
        try:
            elements = await page.query_selector_all(pattern['selector'])
            for element in elements:
                # Extract sitekey using multiple methods
                sitekey = await _extract_sitekey(element)
                
                # Check if element is visible and has dimensions
                is_visible = await element.is_visible()
                bounding_box = None
                try:
                    bounding_box = await element.bounding_box()
                except:
                    pass
                
                # If we found a sitekey or the element is visible, it's likely a valid challenge
                if sitekey or (is_visible and bounding_box and bounding_box['width'] > 0):
                    element_id = await element.get_attribute('id')
                    element_class = await element.get_attribute('class')
                    
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"🎯 Detected: {pattern['type']} - sitekey: {sitekey}, visible: {is_visible}")
                    
                    return {
                        'detected': True,
                        'type': pattern['type'],
                        'sitekey': sitekey,
                        'url': page.url,
                        'selector': pattern['selector'],
                        'element_id': element_id,
                        'element_class': element_class,
                        'visible': is_visible,
                        'auto_solved': False
                    }
                    
        except Exception as e:
            logger.debug(f"Error checking pattern {pattern['selector']}: {e}")
    
    return None

async def _extract_sitekey(element) -> Optional[str]:
    """Extract sitekey from element using multiple methods"""
    # Primary sitekey attributes (in order of preference)
    sitekey_attrs = [
        'data-sitekey',
        'data-cf-turnstile-sitekey', 
        'data-turnstile-sitekey',
        'data-captcha-sitekey',
        'data-site-key',
        'sitekey'
    ]
    
    for attr in sitekey_attrs:
        try:
            sitekey = await element.get_attribute(attr)
            if sitekey and len(sitekey) > 10:  # Valid sitekeys are longer than 10 chars
                return sitekey
        except:
            continue
    
    return None


class UnifiedTurnstileHandler:
    """Unified handler for all Turnstile/Cloudflare bypass methods"""
    
    def __init__(self, user_agent: str = None, proxy: str = None):
        self.user_agent = user_agent
        self.proxy = proxy
        self.dropbox_uploader = DropboxUploader() if DROPBOX_ENABLED else None
        self.solver_manager = get_solver_manager()
        
        # Known Epic Games sitekeys
        self.epic_sitekeys = [
            "0x4AAAAAAADnPIDROzLVaoAo",
            "0x4AAAAAAADnPIDROzLVaoAp", 
            "0x4AAAAAAADnPIDROzLVaoAq",
            "0x4AAAAAAADnPIDROzLVaoAr"
        ]
    
    async def detect_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Enhanced detection for Turnstile/Cloudflare challenges with improved waiting and sitekey extraction
        Returns challenge info or None if no challenge detected
        """
        try:
            # Use the enhanced global detection function
            return await detect_turnstile_challenge(page, max_wait_time=30)
        except Exception as e:
            logger.error(f"❌ Error detecting Turnstile challenge: {str(e)}")
            return {"detected": False, "error": str(e)}
    
    async def solve_with_turnstile_solver(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 1: Solve using the primary Turnstile solver HTTP API"""
        if not challenge_info.get("sitekey"):
            return {"success": False, "error": "No sitekey available for Turnstile solver"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🚀 Attempting primary Turnstile solver via HTTP API...")
            
            start_time = time.time()
            
            # Build request URL for Turnstile API
            api_url = f"http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}/turnstile"
            params = {
                "url": challenge_info["url"],
                "sitekey": challenge_info["sitekey"]
            }
            
            # Add optional parameters if present
            if challenge_info.get("action"):
                params["action"] = challenge_info["action"]
            if challenge_info.get("cdata"):
                params["cdata"] = challenge_info["cdata"]
            
            # Make initial request to start solving
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 202:
                        error_text = await response.text()
                        return {"success": False, "error": f"Turnstile API error: {response.status} - {error_text}"}
                    
                    result_data = await response.json()
                    task_id = result_data.get("task_id")
                    
                    if not task_id:
                        return {"success": False, "error": "No task ID received from Turnstile API"}
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🔄 Turnstile task created with ID: {task_id}")
            
            # Poll for results
            result_url = f"http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}/result"
            max_attempts = TURNSTILE_TIMEOUT  # Use timeout setting as max attempts (1 attempt per second)
            
            for attempt in range(max_attempts):
                await asyncio.sleep(1)  # Wait 1 second between polls
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(result_url, params={"id": task_id}, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                # Turnstile API returns plain text, not JSON
                                token = await response.text()
                                token = token.strip()  # Remove any whitespace
                                
                                # Check if we have a successful result
                                if token and token != "CAPTCHA_NOT_READY" and token != "CAPTCHA_FAIL":
                                    elapsed_time = round(time.time() - start_time, 3)
                                    
                                    if DEBUG_ENHANCED_FEATURES:
                                        logger.info(f"✅ Primary Turnstile solver successful in {elapsed_time}s")
                                    
                                    return {
                                        "success": True,
                                        "token": token,
                                        "method": "turnstile_solver",
                                        "elapsed_time": elapsed_time
                                    }
                                elif token == "CAPTCHA_FAIL":
                                    elapsed_time = round(time.time() - start_time, 3)
                                    return {
                                        "success": False,
                                        "error": "Turnstile solver failed to solve challenge",
                                        "elapsed_time": elapsed_time
                                    }
                                # If CAPTCHA_NOT_READY, continue polling
                            elif response.status == 422:
                                # Challenge failed
                                elapsed_time = round(time.time() - start_time, 3)
                                return {
                                    "success": False,
                                    "error": "Turnstile challenge failed",
                                    "elapsed_time": elapsed_time
                                }
                            elif response.status == 400:
                                error_text = await response.text()
                                return {"success": False, "error": f"Invalid task ID: {error_text}"}
                                
                except asyncio.TimeoutError:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.warning(f"⚠️ Turnstile API timeout on attempt {attempt + 1}")
                    continue
                except Exception as poll_error:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.warning(f"⚠️ Turnstile API poll error: {poll_error}")
                    continue
            
            # Timeout reached
            elapsed_time = round(time.time() - start_time, 3)
            return {
                "success": False,
                "error": f"Turnstile solver timeout after {elapsed_time}s",
                "elapsed_time": elapsed_time
            }
                
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3) if 'start_time' in locals() else 0
            logger.error(f"❌ Turnstile solver HTTP API error: {str(e)}")
            return {"success": False, "error": str(e), "elapsed_time": elapsed_time}
    
    async def solve_with_botsforge(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 2: Solve using BotsForge CloudFlare solver HTTP API"""
        # Require a real sitekey from the current page (no static defaults)
        if not (challenge_info.get('sitekey') and isinstance(challenge_info.get('sitekey'), str) and challenge_info.get('sitekey').startswith('0x')):
            return {"success": False, "error": "BotsForge requires a sitekey from the current page"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🔄 Attempting BotsForge CloudFlare solver via HTTP API...")
            
            start_time = time.time()
            
            # Get API key from configuration (auto-generated by BotsForge server)
            api_key = BOTSFORGE_API_KEY or 'default-api-key'
            
            # Build createTask request payload
            create_task_payload = {
                "clientKey": api_key,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": challenge_info["url"],
                    "websiteKey": challenge_info["sitekey"],
                    "metadata": {
                        "action": challenge_info.get("action", ""),
                        "cdata": challenge_info.get("cdata")
                    }
                }
            }
            
            # Remove None values from metadata
            if create_task_payload["task"]["metadata"]["cdata"] is None:
                del create_task_payload["task"]["metadata"]["cdata"]
            
            # Make createTask request
            create_task_url = f"http://{BOTSFORGE_SERVICE_HOST}:{BOTSFORGE_SERVICE_PORT}/createTask"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    create_task_url, 
                    json=create_task_payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {"success": False, "error": f"BotsForge createTask error: {response.status} - {error_text}"}
                    
                    result_data = await response.json()
                    task_id = result_data.get("taskId")
                    
                    if not task_id or result_data.get("errorId", 0) != 0:
                        error_desc = result_data.get("errorDescription", "Unknown error")
                        return {"success": False, "error": f"BotsForge createTask failed: {error_desc}"}
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🔄 BotsForge task created with ID: {task_id}")
            
            # Poll for results using getTaskResult
            get_result_payload = {
                "clientKey": api_key,
                "taskId": task_id
            }
            
            get_result_url = f"http://{BOTSFORGE_SERVICE_HOST}:{BOTSFORGE_SERVICE_PORT}/getTaskResult"
            max_attempts = 60  # 60 attempts with 2-second intervals = 2 minutes max
            
            for attempt in range(max_attempts):
                await asyncio.sleep(2)  # Wait 2 seconds between polls
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            get_result_url,
                            json=get_result_payload,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status == 200:
                                result_data = await response.json()
                                
                                if result_data.get("errorId", 0) != 0:
                                    error_desc = result_data.get("errorDescription", "Unknown error")
                                    return {"success": False, "error": f"BotsForge task error: {error_desc}"}
                                
                                status = result_data.get("status")
                                
                                if status == "ready":
                                    solution = result_data.get("solution", {})
                                    token = solution.get("token")
                                    
                                    if token:
                                        elapsed_time = round(time.time() - start_time, 3)
                                        
                                        if DEBUG_ENHANCED_FEATURES:
                                            logger.info(f"✅ BotsForge solver successful in {elapsed_time}s")
                                        
                                        return {
                                            "success": True,
                                            "token": token,
                                            "method": "botsforge",
                                            "elapsed_time": elapsed_time
                                        }
                                    else:
                                        return {"success": False, "error": "BotsForge returned empty token"}
                                
                                elif status == "error":
                                    error_desc = result_data.get("errorDescription", "Task failed")
                                    return {"success": False, "error": f"BotsForge task failed: {error_desc}"}
                                
                                # If status is "processing" or "idle", continue polling
                                if DEBUG_ENHANCED_FEATURES and attempt % 10 == 0:  # Log every 20 seconds
                                    logger.info(f"🔄 BotsForge task status: {status} (attempt {attempt + 1})")
                            
                            else:
                                if DEBUG_ENHANCED_FEATURES:
                                    logger.warning(f"⚠️ BotsForge API returned status {response.status}")
                                
                except asyncio.TimeoutError:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.warning(f"⚠️ BotsForge API timeout on attempt {attempt + 1}")
                    continue
                except Exception as poll_error:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.warning(f"⚠️ BotsForge API poll error: {poll_error}")
                    continue
            
            # Timeout reached
            elapsed_time = round(time.time() - start_time, 3)
            return {
                "success": False,
                "error": f"BotsForge solver timeout after {elapsed_time}s",
                "elapsed_time": elapsed_time
            }
                
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3) if 'start_time' in locals() else 0
            logger.error(f"❌ BotsForge solver HTTP API error: {str(e)}")
            return {"success": False, "error": str(e), "elapsed_time": elapsed_time}
    
    async def solve_with_drission_bypass(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 3: Solve using CloudFlare bypasser (supports both DrissionPage and Patchright + Camoufox)"""
        if not self.solver_manager.is_solver_available('drission_bypass'):
            return {"success": False, "error": "CloudFlare bypasser not available"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🔄 Attempting CloudFlare bypasser as fallback...")
            
            # Import the updated CloudflareBypasser
            from solvers.cloudflare_bypass import CloudflareBypasser
            
            # Get solver components from solver manager
            components = self.solver_manager.get_solver_components('drission_bypass')
            if not components:
                return {"success": False, "error": "CloudFlare bypasser components not available"}
            
            # Try Patchright + Camoufox first (preferred)
            if components.get('camoufox_class') and components.get('patchright_async'):
                return await self._use_patchright_camoufox_bypasser(challenge_info, components)
            
            # Fallback to DrissionPage if available
            elif components.get('page_class') and components.get('options_class'):
                return await self._use_drission_bypasser(challenge_info, components)
            
            else:
                return {"success": False, "error": "No suitable bypasser components available"}
                
        except Exception as e:
            logger.error(f"❌ CloudFlare bypasser error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _use_patchright_camoufox_bypasser(self, challenge_info: Dict[str, Any], components: Dict) -> Dict[str, Any]:
        """Use Patchright + Camoufox with CloudFlare bypasser"""
        try:
            from solvers.cloudflare_bypass import CloudflareBypasser
            
            AsyncCamoufox = components['camoufox_class']
            
            # Create Camoufox browser with stealth settings
            camoufox = AsyncCamoufox(
                headless=HEADLESS,
                humanize=True,
                geoip=True,
                screen=True,
                fonts=True,
                addons=True,
                safe_mode=False
            )
            
            browser = await camoufox.launch()
            context_options = {'viewport': {'width': 1920, 'height': 1080}}
            
            # Add proxy and user agent if available
            if self.proxy:
                if '@' in self.proxy:
                    auth_part, host_part = self.proxy.split('@')
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        context_options['proxy'] = {
                            'server': f"http://{host_part}",
                            'username': username,
                            'password': password
                        }
                else:
                    context_options['proxy'] = {'server': f"http://{self.proxy}"}
            
            if self.user_agent:
                context_options['user_agent'] = self.user_agent
            
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            
            try:
                # Navigate to challenge URL
                await page.goto(challenge_info["url"], wait_until='domcontentloaded', timeout=30000)
                
                # Use CloudflareBypasser with Patchright page
                bypasser = CloudflareBypasser(page, max_retries=3, log=DEBUG_ENHANCED_FEATURES)
                success = await bypasser.bypass()
                
                if success:
                    # Extract token and cookies
                    token = None
                    try:
                        turnstile_inputs = await page.query_selector_all('input[name*="turnstile"], input[name*="cf-turnstile"]')
                        for input_elem in turnstile_inputs:
                            token_value = await input_elem.get_attribute('value')
                            if token_value and len(token_value) > 10:
                                token = token_value
                                break
                    except:
                        pass
                    
                    cookies = {}
                    try:
                        cookie_list = await context.cookies()
                        cookies = {cookie['name']: cookie['value'] for cookie in cookie_list}
                    except:
                        pass
                    
                    user_agent = None
                    try:
                        user_agent = await page.evaluate('navigator.userAgent')
                    except:
                        pass
                    
                    return {
                        "success": True,
                        "method": "patchright_camoufox_bypass",
                        "token": token,
                        "cookies": cookies,
                        "user_agent": user_agent or self.user_agent,
                        "final_url": page.url
                    }
                else:
                    return {"success": False, "error": "CloudFlare bypass failed"}
                    
            finally:
                try:
                    await page.close()
                    await context.close()
                    await browser.close()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"❌ Patchright + Camoufox bypasser error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _use_drission_bypasser(self, challenge_info: Dict[str, Any], components: Dict) -> Dict[str, Any]:
        """Use DrissionPage with CloudFlare bypasser (fallback)"""
        try:
            from solvers.cloudflare_bypass import CloudflareBypasser
            
            PageClass = components['page_class']
            OptionsClass = components['options_class']
            
            # Create DrissionPage options
            options = OptionsClass().auto_port()
            options.headless(True)
            options.set_argument("--no-sandbox")
            options.set_argument("--disable-gpu")
            options.set_argument("--disable-dev-shm-usage")
            
            if self.user_agent:
                options.set_user_agent(self.user_agent)
            
            if self.proxy:
                if '@' in self.proxy:
                    auth_part, host_part = self.proxy.split('@')
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        options.set_proxy(f"http://{host_part}")
                        options.set_argument(f"--proxy-auth={username}:{password}")
                else:
                    options.set_proxy(f"http://{self.proxy}")
            
            # Create driver and navigate
            driver = PageClass(addr_or_opts=options)
            
            try:
                driver.get(challenge_info["url"])
                
                # Use CloudflareBypasser with DrissionPage
                bypasser = CloudflareBypasser(driver, max_retries=3, log=DEBUG_ENHANCED_FEATURES)
                success = await bypasser.bypass()
                
                if success:
                    # Extract token and cookies
                    token = None
                    try:
                        turnstile_inputs = driver.eles("tag:input")
                        for input_elem in turnstile_inputs:
                            if "name" in input_elem.attrs and "cf-turnstile-response" in input_elem.attrs["name"]:
                                token = input_elem.attrs.get("value", "")
                                if token:
                                    break
                    except:
                        pass
                    
                    cookies = {}
                    try:
                        cookies = {cookie.get("name", ""): cookie.get("value", "") for cookie in driver.cookies()}
                    except:
                        pass
                    
                    return {
                        "success": True,
                        "method": "drission_bypass",
                        "token": token,
                        "cookies": cookies,
                        "user_agent": driver.user_agent if hasattr(driver, 'user_agent') else self.user_agent
                    }
                else:
                    return {"success": False, "error": "CloudFlare bypass failed"}
                    
            finally:
                try:
                    driver.quit()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"❌ DrissionPage bypasser error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def take_screenshot_and_upload(self, page: Page, account_info: str = "") -> Optional[str]:
        """Take screenshot on successful login and upload to Dropbox"""
        if not self.dropbox_uploader:
            return None
        
        try:
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            
            # Generate filename with timestamp
            timestamp = int(time.time())
            filename = f"successful_login_{timestamp}_{account_info.replace(':', '_').replace('@', '_at_')}.png"
            
            # Upload to Dropbox
            dropbox_path = await self.dropbox_uploader.upload_screenshot(screenshot_bytes, filename)
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"📸 Screenshot uploaded to Dropbox: {dropbox_path}")
            
            return dropbox_path
            
        except Exception as e:
            logger.error(f"❌ Error taking screenshot or uploading: {str(e)}")
            return None
    
    async def inject_turnstile_token(self, page: Page, token: str):
        """Inject the solved Turnstile token into the current page"""
        try:
            # Find the turnstile response input field
            response_input = await page.query_selector('input[name="cf-turnstile-response"]')
            if response_input:
                await response_input.fill(token)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info("✅ Turnstile token injected into response field")
            else:
                # Create the response field if it doesn't exist
                await page.evaluate(f"""
                    () => {{
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'cf-turnstile-response';
                        input.value = '{token}';
                        document.body.appendChild(input);
                    }}
                """)
                if DEBUG_ENHANCED_FEATURES:
                    logger.info("✅ Turnstile response field created and token injected")
                
        except Exception as e:
            logger.warning(f"⚠️ Error injecting Turnstile token: {e}")
    
    async def solve_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Main method to solve Turnstile challenges using all available methods
        Implements proper fallback chain: Primary -> Fallback1 -> Fallback2
        """
        try:
            start_time = time.time()
            
            # First detect the challenge
            challenge_info = await self.detect_turnstile_challenge(page)
            
            if not challenge_info.get("detected"):
                return {"success": True, "status": "no_challenge"}
            
            # Take a screenshot when a challenge is detected
            try:
                await self.take_screenshot_and_upload(page, "turnstile_detected")
            except Exception:
                pass

            if DEBUG_ENHANCED_FEATURES:
                logger.info("🎯 Attempting to solve Turnstile/Cloudflare challenge...")
            
            # If no sitekey extracted at all, go straight to DrissionPage bypass
            if not challenge_info.get("sitekey"):
                if self.solver_manager.is_solver_available('drission_bypass'):
                    result = self.solve_with_drission_bypass(challenge_info)
                    if result.get('success'):
                        # Apply cookies if any
                        if result.get('cookies'):
                            try:
                                await page.context.add_cookies([
                                    {"name": name, "value": value, "domain": urlparse(challenge_info["url"]).netloc}
                                    for name, value in result['cookies'].items() if name and value
                                ])
                            except Exception as e:
                                logger.warning(f"⚠️ Error applying cookies: {e}")
                        return result

            # Sequential solver attempts with proper error handling
            solvers_attempted = []
            
            # Method 1: Try primary Turnstile solver first (HTTP API)
            if challenge_info.get("sitekey"):
                logger.info("🎯 Attempting Method 1: Primary Turnstile solver...")
                solvers_attempted.append("turnstile_solver")
                
                try:
                    result = await self.solve_with_turnstile_solver(challenge_info)
                    if result.get("success"):
                        logger.info("✅ Method 1 (Turnstile solver) succeeded!")
                        # Inject token into page
                        if result.get("token"):
                            await self.inject_turnstile_token(page, result["token"])
                        return result
                    else:
                        logger.warning(f"❌ Method 1 failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"❌ Method 1 exception: {e}")
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.warning("⚠️ Primary Turnstile solver failed, trying fallback 1...")
            else:
                logger.info("ℹ️ Skipping Method 1 (no sitekey available)")
            
            # Method 2: Try BotsForge CloudFlare solver (HTTP API)
            logger.info("🎯 Attempting Method 2: BotsForge solver...")
            solvers_attempted.append("botsforge")
            
            try:
                result = await self.solve_with_botsforge(challenge_info)
                if result.get("success"):
                    logger.info("✅ Method 2 (BotsForge solver) succeeded!")
                    # Inject token into page if available
                    if result.get("token"):
                        await self.inject_turnstile_token(page, result["token"])
                    return result
                else:
                    logger.warning(f"❌ Method 2 failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"❌ Method 2 exception: {e}")
            
            if DEBUG_ENHANCED_FEATURES:
                logger.warning("⚠️ BotsForge solver failed, trying fallback 2...")
            
            # Method 3: Try DrissionPage bypasser as last resort
            if self.solver_manager.is_solver_available('drission_bypass'):
                logger.info("🎯 Attempting Method 3: DrissionPage bypasser...")
                solvers_attempted.append("drission_bypass")
                
                try:
                    result = self.solve_with_drission_bypass(challenge_info)
                    if result.get("success"):
                        logger.info("✅ Method 3 (DrissionPage bypasser) succeeded!")
                        # Apply cookies and user agent to current page if available
                        if result.get("cookies"):
                            try:
                                await page.context.add_cookies([
                                    {"name": name, "value": value, "domain": urlparse(challenge_info["url"]).netloc}
                                    for name, value in result["cookies"].items()
                                    if name and value
                                ])
                            except Exception as e:
                                logger.warning(f"⚠️ Error applying cookies: {e}")
                        
                        return result
                    else:
                        logger.warning(f"❌ Method 3 failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"❌ Method 3 exception: {e}")
            else:
                logger.warning("⚠️ Method 3 (DrissionPage bypasser) not available")
            
            # All methods failed
            elapsed_time = round(time.time() - start_time, 3)
            logger.error(f"❌ All Turnstile solving methods failed. Attempted: {', '.join(solvers_attempted)}")
            try:
                await self.take_screenshot_and_upload(page, "turnstile_failed")
            except Exception:
                pass
            return {
                "success": False, 
                "status": "captcha",
                "error": f"All solving methods failed. Attempted: {', '.join(solvers_attempted)}",
                "elapsed_time": elapsed_time,
                "solvers_attempted": solvers_attempted
            }
            
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            logger.error(f"❌ Error solving Turnstile challenge: {str(e)}")
            try:
                await self.take_screenshot_and_upload(page, "turnstile_error")
            except Exception:
                pass
            return {
                "success": False,
                "status": "error", 
                "error": str(e),
                "elapsed_time": elapsed_time
            }
    
    async def wait_for_turnstile_completion(self, page: Page, timeout: int = 30) -> bool:
        """Wait for Turnstile challenge to be completed on the page"""
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("⏳ Waiting for Turnstile completion...")
            
            # Wait for the turnstile response field to have a value
            await page.wait_for_function(
                """
                () => {
                    const responseField = document.querySelector('input[name="cf-turnstile-response"]');
                    return responseField && responseField.value && responseField.value.length > 0;
                }
                """,
                timeout=timeout * 1000
            )
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info("✅ Turnstile challenge completed")
            return True
            
        except Exception as e:
            logger.warning(f"❌ Turnstile completion timeout or error: {e}")
            return False


# Global instance factory
def create_turnstile_handler(user_agent: str = None, proxy: str = None) -> UnifiedTurnstileHandler:
    """Create a new UnifiedTurnstileHandler instance with the given settings"""
    return UnifiedTurnstileHandler(user_agent=user_agent, proxy=proxy)