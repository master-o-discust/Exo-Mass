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
        Enhanced detection for Turnstile/Cloudflare challenges
        Returns challenge info or None if no challenge detected
        """
        try:
            # Wait a moment for page to load
            await asyncio.sleep(2)
            
            # Check for multiple Cloudflare indicators (enhanced detection)
            indicators = [
                "Just a moment",
                "Checking your browser",
                "Please wait while we check your browser",
                "Cloudflare",
                "cf-turnstile",
                "turnstile",
                "challenge-form",
                "ray id",
                "enable javascript and cookies to continue",
                "something went wrong",
                "verifying you are human",
                "browser verification",
                "window._cf_chl_opt",
                "challenge-platform",
                "cdn-cgi/challenge-platform",
                "orchestrate/chl_page",
                "cf_chl_opt",
                "cray:",
                "czone:",
                "ctype:",
                "performance & security by cloudflare"
            ]
            
            page_content = await page.content()
            page_title = await page.title()
            current_url = page.url
            
            # Check title and content for indicators
            challenge_detected = False
            detected_indicator = None
            for indicator in indicators:
                if indicator.lower() in page_title.lower() or indicator.lower() in page_content.lower():
                    challenge_detected = True
                    detected_indicator = indicator
                    break
            
            # Also check URL patterns for CloudFlare error pages
            if not challenge_detected:
                url_indicators = ['/error?', '__cf_chl', 'cloudflare']
                for url_indicator in url_indicators:
                    if url_indicator in current_url.lower():
                        challenge_detected = True
                        detected_indicator = f"URL pattern: {url_indicator}"
                        break
            
            if not challenge_detected:
                return {"detected": False}
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🔍 Turnstile/Cloudflare challenge detected: {detected_indicator}")
            
            # Take a screenshot of the challenge page for debugging
            try:
                await self.take_screenshot_and_upload(page, f"challenge_detected_{detected_indicator.replace(' ', '_')}")
            except Exception:
                pass
            
            # Try multiple methods to find Turnstile sitekey
            challenge_info = {
                "detected": True,
                "url": current_url,
                "sitekey": None,
                "action": None,
                "cdata": None,
                "method": "turnstile_solver",  # Default to primary method
                "indicator": detected_indicator
            }
            
            # Method 1: Look for Turnstile widget elements
            turnstile_elements = await page.query_selector_all('[data-sitekey]')
            if turnstile_elements:
                element = turnstile_elements[0]
                sitekey = await element.get_attribute('data-sitekey')
                action = await element.get_attribute('data-action')
                cdata = await element.get_attribute('data-cdata')
                
                challenge_info.update({
                    "sitekey": sitekey,
                    "action": action,
                    "cdata": cdata
                })
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"🎯 Found Turnstile widget with sitekey: {sitekey}")
            
            # Method 2: Look for cf-turnstile elements
            if not challenge_info["sitekey"]:
                cf_elements = await page.query_selector_all('.cf-turnstile')
                for element in cf_elements:
                    sitekey = await element.get_attribute('data-sitekey')
                    if sitekey:
                        challenge_info["sitekey"] = sitekey
                        challenge_info["action"] = await element.get_attribute('data-action')
                        challenge_info["cdata"] = await element.get_attribute('data-cdata')
                        if DEBUG_ENHANCED_FEATURES:
                            logger.info(f"🎯 Found cf-turnstile element with sitekey: {sitekey}")
                        break
            
            # Method 3: Search page source for sitekey patterns
            if not challenge_info["sitekey"]:
                import re
                # Look for sitekey in various JavaScript patterns
                sitekey_patterns = [
                    r'sitekey["\']?\s*[:=]\s*["\']([0-9a-fA-F_x]+)["\']',
                    r'data-sitekey["\']?\s*[:=]\s*["\']([0-9a-fA-F_x]+)["\']',
                    r'["\']sitekey["\']:\s*["\']([0-9a-fA-F_x]+)["\']',
                    r'turnstile.*?["\']([0-9a-fA-F_x]{26,})["\']',
                ]
                
                for pattern in sitekey_patterns:
                    matches = re.findall(pattern, page_content, re.IGNORECASE)
                    for match in matches:
                        if match.startswith('0x') and len(match) >= 26:
                            challenge_info["sitekey"] = match
                            if DEBUG_ENHANCED_FEATURES:
                                logger.info(f"🎯 Found sitekey in page source: {match}")
                            break
                    if challenge_info["sitekey"]:
                        break
            
            # Method 4: Try to find known Epic Games sitekeys in page source
            if not challenge_info["sitekey"]:
                for sitekey in self.epic_sitekeys:
                    if sitekey in page_content:
                        challenge_info["sitekey"] = sitekey
                        if DEBUG_ENHANCED_FEATURES:
                            logger.info(f"🎯 Found Epic Games sitekey in page: {sitekey}")
                        break
                
                # If no specific sitekey found, will try fallback methods
                if not challenge_info["sitekey"]:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info("🔄 No sitekey found, will use fallback methods")
                    # Take screenshot when no sitekey found
                    try:
                        await self.take_screenshot_and_upload(page, "no_sitekey_found")
                    except Exception:
                        pass
                else:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"✅ Sitekey detection complete: {challenge_info['sitekey']}")
                    # Take screenshot when sitekey found
                    try:
                        await self.take_screenshot_and_upload(page, f"sitekey_found_{challenge_info['sitekey'][:10]}")
                    except Exception:
                        pass
            
            return challenge_info
            
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
    
    def solve_with_drission_bypass(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 3: Solve using DrissionPage CloudFlare bypasser"""
        if not self.solver_manager.is_solver_available('drission_bypass'):
            return {"success": False, "error": "DrissionPage bypasser not available"}
        
        try:
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🔄 Attempting DrissionPage CloudFlare bypasser...")
            
            # Setup ChromiumOptions with our settings (use manager-provided classes if needed)
            components = self.solver_manager.get_solver_components('drission_bypass') if self.solver_manager.is_solver_available('drission_bypass') else None
            OptionsClass = (ChromiumOptions or (components and components.get('options_class')))
            PageClass = (ChromiumPage or (components and components.get('page_class')))
            BypasserClass = (CloudflareBypasser or (components and components.get('bypasser_class')))
            if not OptionsClass or not PageClass or not BypasserClass:
                raise ImportError('Drission bypass components not available')
            options = OptionsClass().auto_port()
            options.headless(True)
            options.set_argument("--no-sandbox")
            options.set_argument("--disable-gpu")
            options.set_argument("--disable-dev-shm-usage")
            
            # Set user agent if available
            if self.user_agent:
                options.set_user_agent(self.user_agent)
            
            # Set proxy if available
            if self.proxy:
                # Parse proxy format: username:password@host:port
                if '@' in self.proxy:
                    auth_part, host_part = self.proxy.split('@')
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                        options.set_proxy(f"http://{host_part}")
                        options.set_argument(f"--proxy-auth={username}:{password}")
                    else:
                        options.set_proxy(f"http://{self.proxy}")
                else:
                    options.set_proxy(f"http://{self.proxy}")
            
            # Create driver
            driver = PageClass(addr_or_opts=options)
            
            try:
                # Navigate to the URL
                driver.get(challenge_info["url"])
                
                # Use CloudflareBypasser
                cf_bypasser = BypasserClass(driver, max_retries=5, log=DEBUG_ENHANCED_FEATURES)
                cf_bypasser.bypass()
                
                # Check if bypass was successful
                if cf_bypasser.is_bypassed():
                    # Try to extract Turnstile token if available
                    token = None
                    try:
                        # Look for cf-turnstile-response input
                        turnstile_inputs = driver.eles("tag:input")
                        for input_elem in turnstile_inputs:
                            if "name" in input_elem.attrs and "cf-turnstile-response" in input_elem.attrs["name"]:
                                token = input_elem.attrs.get("value", "")
                                if token:
                                    break
                    except:
                        pass
                    
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info("✅ DrissionPage bypass successful")
                    
                    return {
                        "success": True,
                        "method": "drission_bypass",
                        "token": token,
                        "cookies": {cookie.get("name", ""): cookie.get("value", "") for cookie in driver.cookies()},
                        "user_agent": driver.user_agent
                    }
                else:
                    return {"success": False, "error": "DrissionPage bypass failed"}
                    
            finally:
                driver.quit()
                
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