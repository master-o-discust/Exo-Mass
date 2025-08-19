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
from utils.enhanced_sitekey_extractor import EnhancedSitekeyExtractor

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
    
    check_interval = 1  # Check every 1 second for faster detection
    checks_performed = 0
    
    while time.time() - start_time < max_wait_time:
        await asyncio.sleep(check_interval)
        checks_performed += 1
        
        # Force page to execute any pending JavaScript and trigger Turnstile loading
        try:
            await page.evaluate("""
                () => {
                    // Force document ready state check
                    if (document.readyState === 'complete') {
                        // Try to trigger any pending Turnstile initialization
                        if (window.turnstile && window.turnstile.render) {
                            console.log('Turnstile API available');
                        }
                        
                        // Check for any pending challenge widgets
                        const challengeElements = document.querySelectorAll('[data-sitekey], .cf-turnstile, .turnstile-wrapper');
                        if (challengeElements.length > 0) {
                            console.log('Found challenge elements:', challengeElements.length);
                        }
                        
                        // Trigger any pending iframe loads
                        const iframes = document.querySelectorAll('iframe');
                        iframes.forEach(iframe => {
                            if (iframe.src && iframe.src.includes('challenges.cloudflare.com')) {
                                console.log('Found Cloudflare challenge iframe');
                            }
                        });
                    }
                    return document.readyState;
                }
            """)
        except:
            pass
        
        if DEBUG_ENHANCED_FEATURES and checks_performed % 6 == 0:  # Log every 6 seconds
            elapsed = int(time.time() - start_time)
            logger.info(f"🔄 Still searching for Turnstile... ({elapsed}s elapsed)")
            
            # Also log page state for debugging
            try:
                current_url = page.url
                page_title = await page.title()
                logger.info(f"   Current URL: {current_url}")
                logger.info(f"   Page title: {page_title}")
            except:
                pass
        
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
    """Check a list of Turnstile patterns - sitekey extraction handled by EnhancedSitekeyExtractor"""
    for pattern in patterns:
        try:
            elements = await page.query_selector_all(pattern['selector'])
            for element in elements:
                # Check if element is visible and has dimensions
                is_visible = await element.is_visible()
                bounding_box = None
                try:
                    bounding_box = await element.bounding_box()
                except:
                    pass
                
                # If the element is visible, it's likely a valid challenge
                if is_visible and bounding_box and bounding_box['width'] > 0:
                    element_id = await element.get_attribute('id')
                    element_class = await element.get_attribute('class')
                    
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"🎯 Detected: {pattern['type']} - sitekey: None, visible: {is_visible}")
                    
                    return {
                        'detected': True,
                        'type': pattern['type'],
                        'sitekey': None,  # Will be extracted by EnhancedSitekeyExtractor
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




class UnifiedTurnstileHandler:
    """Unified handler for all Turnstile/Cloudflare bypass methods"""
    
    def __init__(self, user_agent: str = None, proxy: str = None):
        self.user_agent = user_agent
        self.proxy = proxy
        self.dropbox_uploader = DropboxUploader() if DROPBOX_ENABLED else None
        self.solver_manager = get_solver_manager()
        
        # NO HARDCODED SITEKEYS - Each challenge has its own unique sitekey
        # We extract the actual sitekey from the current page/challenge
    
    async def detect_turnstile_challenge(self, page: Page) -> Dict[str, Any]:
        """
        Enhanced detection for Turnstile/Cloudflare challenges using the new enhanced extractor
        Returns challenge info with actual sitekey from current page
        """
        try:
            # Use the enhanced global detection function for basic detection
            basic_detection = await detect_turnstile_challenge(page, max_wait_time=30)
            
            if basic_detection.get('detected'):
                # Use the enhanced sitekey extractor to get the ACTUAL sitekey
                logger.info("🔍 Using enhanced sitekey extraction for detected challenge...")
                actual_sitekey = await EnhancedSitekeyExtractor.extract_sitekey_comprehensive(page)
                
                if actual_sitekey:
                    basic_detection['sitekey'] = actual_sitekey
                    logger.info(f"✅ Enhanced detection found actual sitekey: {actual_sitekey}")
                else:
                    logger.warning("⚠️ Enhanced detection could not extract sitekey")
                
                return basic_detection
            else:
                return {"detected": False, "error": "No challenge detected"}
                
        except Exception as e:
            logger.error(f"❌ Error detecting Turnstile challenge: {str(e)}")
            return {"detected": False, "error": str(e)}
    
    async def solve_with_turnstile_solver(self, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """Method 1: Solve using the primary Turnstile solver HTTP API with retry on failure"""
        if not challenge_info.get("sitekey"):
            return {"success": False, "error": "No sitekey available for Turnstile solver"}
        
        page = challenge_info.get('page')
        max_retries = 3  # Maximum number of retries on CAPTCHA_FAIL
        
        for retry_attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                if retry_attempt > 0:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"🔄 Retry attempt {retry_attempt}/{max_retries} - Refreshing page for new challenge...")
                    
                    if page:
                        try:
                            # Refresh the page to get a new challenge
                            await page.reload(wait_until="domcontentloaded", timeout=30000)
                            await asyncio.sleep(3)  # Wait for challenge to load
                            
                            # Check what type of page we're on after refresh
                            page_info = await self.detect_page_type(page)
                            
                            if DEBUG_ENHANCED_FEATURES:
                                logger.info(f"📄 After refresh - Page type: {page_info['page_type']}, Title: {page_info['title']}")
                            
                            if not page_info['is_challenge_page']:
                                # We're no longer on a challenge page
                                if page_info['is_login_page']:
                                    if DEBUG_ENHANCED_FEATURES:
                                        logger.info("✅ Page refresh bypassed challenge - now on login page!")
                                    return {
                                        "success": True,
                                        "method": "page_refresh_bypass",
                                        "status": "challenge_bypassed_by_refresh",
                                        "retry_attempt": retry_attempt
                                    }
                                elif page_info['is_account_page']:
                                    if DEBUG_ENHANCED_FEATURES:
                                        logger.info("✅ Page refresh bypassed challenge - now on account page!")
                                    return {
                                        "success": True,
                                        "method": "page_refresh_bypass",
                                        "status": "challenge_bypassed_to_account",
                                        "retry_attempt": retry_attempt
                                    }
                                else:
                                    if DEBUG_ENHANCED_FEATURES:
                                        logger.info(f"ℹ️ Page refresh led to {page_info['page_type']} page - continuing login process")
                                    return {
                                        "success": True,
                                        "method": "page_refresh_redirect",
                                        "status": f"redirected_to_{page_info['page_type']}",
                                        "retry_attempt": retry_attempt
                                    }
                            
                            # Still on challenge page - try to extract new sitekey
                            from .enhanced_sitekey_extractor import EnhancedSitekeyExtractor
                            extractor = EnhancedSitekeyExtractor()
                            new_sitekey = await extractor.extract_sitekey(page)
                            
                            if new_sitekey:
                                challenge_info["sitekey"] = new_sitekey
                                if DEBUG_ENHANCED_FEATURES:
                                    logger.info(f"✅ New sitekey extracted after refresh: {new_sitekey}")
                            else:
                                if DEBUG_ENHANCED_FEATURES:
                                    logger.warning("⚠️ Could not extract new sitekey after refresh, using original")
                                    
                        except Exception as refresh_error:
                            if DEBUG_ENHANCED_FEATURES:
                                logger.warning(f"⚠️ Page refresh failed: {refresh_error}")
                            # Continue with original challenge info
                
                if DEBUG_ENHANCED_FEATURES:
                    attempt_text = f" (attempt {retry_attempt + 1}/{max_retries + 1})" if retry_attempt > 0 else ""
                    logger.info(f"🚀 Attempting primary Turnstile solver via HTTP API{attempt_text}...")
                
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
                            if retry_attempt < max_retries:
                                if DEBUG_ENHANCED_FEATURES:
                                    logger.warning(f"⚠️ API error, will retry: {response.status} - {error_text}")
                                continue
                            return {"success": False, "error": f"Turnstile API error: {response.status} - {error_text}"}
                        
                        result_data = await response.json()
                        task_id = result_data.get("task_id")
                        
                        if not task_id:
                            if retry_attempt < max_retries:
                                if DEBUG_ENHANCED_FEATURES:
                                    logger.warning("⚠️ No task ID received, will retry")
                                continue
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
                                            "elapsed_time": elapsed_time,
                                            "retry_attempt": retry_attempt
                                        }
                                    elif token == "CAPTCHA_FAIL":
                                        elapsed_time = round(time.time() - start_time, 3)
                                        if retry_attempt < max_retries:
                                            if DEBUG_ENHANCED_FEATURES:
                                                logger.warning(f"❌ CAPTCHA_FAIL received, will refresh page and retry ({retry_attempt + 1}/{max_retries})")
                                            break  # Break out of polling loop to retry with page refresh
                                        else:
                                            return {
                                                "success": False,
                                                "error": f"Turnstile solver failed after {max_retries + 1} attempts",
                                                "elapsed_time": elapsed_time
                                            }
                                    # If CAPTCHA_NOT_READY, continue polling
                                elif response.status == 422:
                                    # Challenge failed
                                    elapsed_time = round(time.time() - start_time, 3)
                                    if retry_attempt < max_retries:
                                        if DEBUG_ENHANCED_FEATURES:
                                            logger.warning(f"⚠️ Challenge failed (422), will retry")
                                        break  # Break out of polling loop to retry
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
                
                # If we reach here, polling timed out
                if retry_attempt < max_retries:
                    elapsed_time = round(time.time() - start_time, 3)
                    if DEBUG_ENHANCED_FEATURES:
                        logger.warning(f"⚠️ Solver timeout after {elapsed_time}s, will refresh and retry")
                    continue
                
                # Final timeout
                elapsed_time = round(time.time() - start_time, 3)
                return {
                    "success": False,
                    "error": f"Turnstile solver timeout after {elapsed_time}s (tried {max_retries + 1} times)",
                    "elapsed_time": elapsed_time
                }
                    
            except Exception as e:
                elapsed_time = round(time.time() - start_time, 3) if 'start_time' in locals() else 0
                if retry_attempt < max_retries:
                    if DEBUG_ENHANCED_FEATURES:
                        logger.warning(f"⚠️ Solver error, will retry: {str(e)}")
                    continue
                logger.error(f"❌ Turnstile solver HTTP API error: {str(e)}")
                return {"success": False, "error": str(e), "elapsed_time": elapsed_time}
        
        # Should never reach here, but just in case
        return {"success": False, "error": "Maximum retries exceeded"}
    
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
    
    async def solve_challenge_with_visible_browser(self, page: Page, challenge_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a visible browser to solve challenges when headless mode fails
        This ensures Turnstile widgets can load properly
        """
        try:
            logger.info("🔧 Creating visible browser for challenge solving...")
            
            # Import browser manager
            from utils.browser_manager import BrowserManager
            
            # Create a new browser manager instance for visible browser
            visible_browser_manager = BrowserManager([self.proxy] if self.proxy else [])
            await visible_browser_manager.initialize()
            
            # Create visible browser
            visible_browser = await visible_browser_manager.create_visible_browser_for_challenges(self.proxy)
            
            # Create context with proper settings for Turnstile
            visible_context = await visible_browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 720},  # Desktop viewport for better widget rendering
                locale="en-US",
                timezone_id="America/New_York",
                java_script_enabled=True,
                permissions=["geolocation", "notifications"]
            )
            
            # Create new page
            visible_page = await visible_context.new_page()
            
            try:
                # Navigate to the same URL as the original page
                current_url = page.url
                logger.info(f"🌐 Navigating visible browser to: {current_url}")
                await visible_page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for page to stabilize
                await asyncio.sleep(3)
                
                # Take screenshot to see what's loaded
                try:
                    await self.take_screenshot_and_upload(visible_page, "visible_browser_challenge_page")
                except:
                    pass
                
                # Now try to detect and solve the challenge in the visible browser
                logger.info("🔍 Detecting Turnstile challenge in visible browser...")
                
                # Wait for Turnstile widget to appear
                turnstile_detected = False
                max_wait = 30
                wait_time = 0
                
                while wait_time < max_wait and not turnstile_detected:
                    # Check for Turnstile iframe
                    turnstile_iframes = await visible_page.query_selector_all('iframe[src*="challenges.cloudflare.com"]')
                    if turnstile_iframes:
                        logger.info("✅ Turnstile iframe detected in visible browser!")
                        turnstile_detected = True
                        break
                    
                    # Check for Turnstile widget
                    turnstile_widgets = await visible_page.query_selector_all('[data-sitekey], .cf-turnstile, .turnstile-wrapper')
                    if turnstile_widgets:
                        logger.info("✅ Turnstile widget detected in visible browser!")
                        turnstile_detected = True
                        break
                    
                    await asyncio.sleep(1)
                    wait_time += 1
                
                if turnstile_detected:
                    logger.info("🎯 Turnstile widget found! Attempting to solve...")
                    
                    # Extract sitekey from visible page
                    sitekey_extractor = EnhancedSitekeyExtractor()
                    sitekey = await sitekey_extractor.extract_sitekey(visible_page)
                    
                    if sitekey:
                        logger.info(f"🔑 Extracted sitekey: {sitekey}")
                        
                        # Try to solve using the primary solver
                        challenge_data = {
                            "url": current_url,
                            "sitekey": sitekey,
                            "user_agent": self.user_agent,
                            "proxy": self.proxy
                        }
                        
                        # Use the primary turnstile solver
                        result = await self._use_turnstile_solver(challenge_data)
                        
                        if result.get("success"):
                            logger.info("✅ Challenge solved successfully with visible browser!")
                            
                            # Copy the solution back to the original page if needed
                            token = result.get("token")
                            if token:
                                try:
                                    # Try to inject the token into the original page
                                    await page.evaluate(f"""
                                        // Try to find and fill the cf-turnstile-response field
                                        const responseField = document.querySelector('[name="cf-turnstile-response"]');
                                        if (responseField) {{
                                            responseField.value = '{token}';
                                        }}
                                        
                                        // Trigger any necessary events
                                        const event = new Event('change', {{ bubbles: true }});
                                        if (responseField) responseField.dispatchEvent(event);
                                    """)
                                    logger.info("✅ Token injected into original page")
                                except Exception as e:
                                    logger.warning(f"⚠️ Could not inject token into original page: {e}")
                            
                            return result
                        else:
                            logger.warning("❌ Challenge solving failed even with visible browser")
                            return {"success": False, "error": "Challenge solving failed in visible browser"}
                    else:
                        logger.warning("❌ Could not extract sitekey from visible browser")
                        return {"success": False, "error": "No sitekey found in visible browser"}
                else:
                    logger.warning("❌ No Turnstile widget found in visible browser")
                    return {"success": False, "error": "No Turnstile widget found in visible browser"}
                    
            finally:
                # Clean up visible browser resources
                try:
                    await visible_page.close()
                    await visible_context.close()
                    await visible_browser.close()
                    await visible_browser_manager.cleanup()
                except Exception as e:
                    logger.warning(f"⚠️ Error cleaning up visible browser: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in visible browser challenge solving: {e}")
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
    
    async def detect_page_type(self, page: Page) -> Dict[str, Any]:
        """Detect what type of page we're currently on"""
        try:
            current_title = await page.title()
            current_url = page.url
            
            # Check for challenge page
            is_challenge_page = (
                "Just a moment" in current_title or 
                "challenge" in current_title.lower() or
                "cloudflare" in current_title.lower() or
                current_url.find("challenge") != -1 or
                "checking your browser" in current_title.lower()
            )
            
            # Check for login page
            is_login_page = (
                "login" in current_url.lower() or
                "sign in" in current_title.lower() or
                ("epic games" in current_title.lower() and "login" in current_title.lower()) or
                current_url.endswith("/id/login") or
                current_url.find("/id/login") != -1
            )
            
            # Check for account/dashboard page (successful login)
            is_account_page = (
                "account" in current_url.lower() or
                "dashboard" in current_url.lower() or
                "profile" in current_url.lower() or
                current_url.find("/account/") != -1
            )
            
            return {
                "title": current_title,
                "url": current_url,
                "is_challenge_page": is_challenge_page,
                "is_login_page": is_login_page,
                "is_account_page": is_account_page,
                "page_type": (
                    "challenge" if is_challenge_page else
                    "login" if is_login_page else
                    "account" if is_account_page else
                    "unknown"
                )
            }
        except Exception as e:
            logger.error(f"❌ Error detecting page type: {e}")
            return {
                "title": "unknown",
                "url": "unknown", 
                "is_challenge_page": False,
                "is_login_page": False,
                "is_account_page": False,
                "page_type": "error"
            }

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
                # If no challenge detected in headless mode, try with visible browser
                # This handles cases where Turnstile widgets don't load in headless mode
                logger.info("🔍 No challenge detected in headless mode, trying visible browser...")
                
                # Check if we're on a challenge page by URL or content
                current_url = page.url
                page_content = await page.content()
                
                challenge_indicators = [
                    "challenges.cloudflare.com" in current_url,
                    "cf-challenge" in current_url,
                    "just a moment" in page_content.lower(),
                    "checking your browser" in page_content.lower(),
                    "please wait" in page_content.lower(),
                    "security check" in page_content.lower(),
                    "one more step" in page_content.lower()
                ]
                
                if any(challenge_indicators):
                    logger.info("🛡️ Challenge page detected by content/URL, using visible browser...")
                    
                    # Set up virtual display and try visible browser
                    from utils.virtual_display import ensure_virtual_display
                    if ensure_virtual_display():
                        logger.info("✅ Virtual display ready, attempting visible browser challenge solving...")
                        visible_result = await self.solve_challenge_with_visible_browser(page, challenge_info)
                        if visible_result.get("success"):
                            return visible_result
                        else:
                            logger.warning("❌ Visible browser challenge solving also failed")
                    else:
                        logger.warning("⚠️ Could not set up virtual display for visible browser")
                
                return {"success": True, "status": "no_challenge"}
            
            # ENHANCED SITEKEY EXTRACTION - Get the ACTUAL sitekey from the current challenge
            logger.info("🔍 Extracting actual sitekey from current challenge...")
            actual_sitekey = await EnhancedSitekeyExtractor.extract_sitekey_comprehensive(page)
            
            if actual_sitekey:
                logger.info(f"✅ Found actual sitekey: {actual_sitekey}")
                challenge_info['sitekey'] = actual_sitekey
            else:
                logger.warning("⚠️ Could not extract sitekey from current challenge")
            
            # Add page object to challenge_info for retry functionality
            challenge_info['page'] = page
            
            # Take a screenshot when a challenge is detected
            try:
                await self.take_screenshot_and_upload(page, "turnstile_detected")
            except Exception:
                pass

            if DEBUG_ENHANCED_FEATURES:
                logger.info("🎯 Attempting to solve Turnstile/Cloudflare challenge...")
                logger.info(f"   Sitekey: {actual_sitekey or 'Not found'}")
            


            # Try available solvers in order of preference
            solvers_attempted = []
            
            # Method 1: Try primary Turnstile solver (HTTP API) with ACTUAL sitekey
            if actual_sitekey and self.solver_manager.is_solver_available('turnstile_solver'):
                logger.info(f"🎯 Trying Primary Turnstile solver with actual sitekey: {actual_sitekey}")
                solvers_attempted.append("turnstile_solver")
                
                try:
                    logger.info(f"🔧 Calling primary solver with challenge_info: {challenge_info}")
                    result = await self.solve_with_turnstile_solver(challenge_info)
                    logger.info(f"🔧 Primary solver returned: {result}")
                    
                    if result.get("success"):
                        logger.info("✅ Primary Turnstile solver succeeded with actual sitekey!")
                        # Inject token into page
                        if result.get("token"):
                            await self.inject_turnstile_token(page, result["token"])
                        return result
                    else:
                        logger.error(f"❌ Primary Turnstile solver failed: {result.get('error', 'Unknown error')}")
                        logger.error(f"❌ Full result: {result}")
                except Exception as e:
                    logger.error(f"❌ Primary Turnstile solver exception: {e}")
                    import traceback
                    logger.error(f"❌ Exception traceback: {traceback.format_exc()}")
            
            # DISABLED: Fallback solvers as requested by user
            # Only use the primary Turnstile solver method
            logger.info("ℹ️ Fallback solvers disabled - using only primary Turnstile solver")
            
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