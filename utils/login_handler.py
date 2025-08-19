"""
Login handler for Epic Games accounts
Handles the actual login process, form filling, and navigation
"""
import asyncio
import logging
import random
from typing import Any, Dict, Optional, Tuple

from config.settings import LOGIN_URL, NAVIGATION_TIMEOUT, DROPBOX_ENABLED
from utils.unified_turnstile_handler import create_turnstile_handler

logger = logging.getLogger(__name__)


class LoginHandler:
    """Handles Epic Games login process"""
    
    def __init__(self, auth_handler, user_agent: str = None, proxy: str = None):
        self.auth_handler = auth_handler
        self.user_agent = user_agent
        self.proxy = proxy
        # Create turnstile handler with our settings
        self.turnstile_handler = create_turnstile_handler(user_agent=user_agent, proxy=proxy)
    
    async def perform_login(self, page: Any, email: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform the complete login process
        """
        try:
            logger.info(f"🔐 {email} - Starting login process...")
            
            # Navigate to login page (includes CloudFlare challenge handling)
            if not await self._navigate_to_login(page, email):
                try:
                    await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_navigate_error")
                except Exception:
                    pass
                return False, {'error': 'Failed to navigate to login page'}
            
            # Check for challenges before filling form
            await self.check_and_handle_challenges_anywhere(page, email, "before_form_fill")
            
            # Fill login form
            if not await self._fill_login_form(page, email, password):
                # Before reporting failure, check if we're on a challenge page
                logger.warning(f"⚠️ {email} - Form filling failed, checking for challenges...")
                if await self.check_and_handle_challenges_anywhere(page, email, "form_fill_failed"):
                    # Challenge was solved, try form filling again
                    logger.info(f"🔄 {email} - Retrying form fill after challenge resolution...")
                    if await self._fill_login_form(page, email, password):
                        logger.info(f"✅ {email} - Form filled successfully after challenge resolution")
                    else:
                        try:
                            await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_fill_form_failed_after_challenge")
                        except Exception:
                            pass
                        return False, {'error': 'Failed to fill login form even after challenge resolution'}
                else:
                    try:
                        await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_fill_form_failed")
                    except Exception:
                        pass
                    return False, {'error': 'Failed to fill login form'}
            
            # Form filling now includes sign in button clicking and challenge handling
            logger.info(f"✅ {email} - Login form processing completed")
            
            # Wait for login to complete and detect outcome
            status, result = await self.auth_handler.detect_outcome_and_extract_auth(page, email)
            
            if status.value == "valid":
                logger.info(f"✅ {email} - Login successful")
                
                # Take screenshot only for Epic Games successful logins and upload to Dropbox
                current_url = page.url
                if DROPBOX_ENABLED and self._is_epic_games_domain(current_url):
                    try:
                        screenshot_path = await self.turnstile_handler.take_screenshot_and_upload(page, email)
                        if screenshot_path:
                            result['screenshot_path'] = screenshot_path
                            logger.info(f"📸 {email} - Epic Games login screenshot saved to Dropbox: {screenshot_path}")
                        else:
                            logger.warning(f"⚠️ {email} - Failed to save Epic Games screenshot to Dropbox")
                    except Exception as e:
                        logger.warning(f"⚠️ {email} - Epic Games screenshot error: {str(e)}")
                elif DROPBOX_ENABLED:
                    logger.debug(f"🔍 {email} - Skipping screenshot (not Epic Games domain): {current_url}")
                
                return True, result
            else:
                logger.info(f"❌ {email} - Login failed: {status.value}")
                return False, result
                
        except Exception as e:
            logger.info(f"❌ {email} - Login error: {str(e)}")
            try:
                await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_login_exception")
            except Exception:
                pass
            return False, {'error': f'Login error: {str(e)}'}
    
    def _is_epic_games_domain(self, url: str) -> bool:
        """Check if the URL is from Epic Games domain"""
        epic_domains = [
            'epicgames.com',
            'www.epicgames.com',
            'store.epicgames.com',
            'launcher.store.epicgames.com',
            'accounts.epicgames.com'
        ]
        
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Check if domain matches any Epic Games domains
            for epic_domain in epic_domains:
                if domain == epic_domain or domain.endswith('.' + epic_domain):
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Error parsing URL {url}: {e}")
            return False
    
    async def _navigate_to_login(self, page: Any, email: str) -> bool:
        """Navigate to Epic Games login page with CloudFlare challenge handling"""
        try:
            logger.info(f"🌐 {email} - Navigating to login page...")
            
            response = await page.goto(LOGIN_URL, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
            
            # Check if we got blocked by CloudFlare (403, 503, or other error codes)
            if not response or response.status not in [200, 403, 503]:
                logger.info(f"❌ {email} - Failed to load login page: {response.status if response else 'No response'}")
                return False
            
            # If we got a 403 or 503, or if we detect CloudFlare challenges, handle them
            if response.status in [403, 503] or await self._has_cloudflare_challenge(page):
                logger.info(f"🛡️ {email} - CloudFlare challenge detected (status: {response.status}), attempting to solve...")
                
                # Handle CloudFlare challenges
                challenge_result = await self.turnstile_handler.solve_turnstile_challenge(page)
                
                if not challenge_result.get('success'):
                    if challenge_result.get('status') == 'captcha':
                        logger.info(f"❌ {email} - Failed to solve CloudFlare challenge: {challenge_result.get('error', 'Unknown error')}")
                        return False
                    elif challenge_result.get('status') == 'no_challenge':
                        logger.info(f"ℹ️ {email} - No challenge detected, but got {response.status} status")
                
                # Wait for page to settle after challenge resolution
                await asyncio.sleep(5)  # Increased wait time for challenge resolution
                
                # Wait for CloudFlare challenges to fully complete
                if not await self._wait_for_challenge_completion(page, email):
                    logger.info(f"❌ {email} - CloudFlare challenge did not complete successfully")
                    return False
                
                # Check if we're now on the correct page
                current_url = page.url
                if response.status in [403, 503] and current_url == LOGIN_URL:
                    # Try to reload the page after challenge resolution
                    logger.info(f"🔄 {email} - Reloading page after challenge resolution...")
                    response = await page.reload(wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
                    if not response or response.status != 200:
                        logger.info(f"❌ {email} - Page still blocked after challenge resolution: {response.status if response else 'No response'}")
                        return False
            
            # Wait for page to be ready
            await asyncio.sleep(2)
            
            # Check if we're on the correct page
            current_url = page.url
            if 'login' not in current_url.lower() and 'signin' not in current_url.lower():
                logger.info(f"⚠️ {email} - Unexpected page after navigation: {current_url}")
            
            logger.info(f"✅ {email} - Successfully navigated to login page")
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Navigation error: {str(e)}")
            return False
    
    async def _has_cloudflare_challenge(self, page: Any) -> bool:
        """Check if the current page has CloudFlare challenges"""
        try:
            # Check for common CloudFlare challenge indicators
            page_content = await page.content()
            cloudflare_indicators = [
                'cloudflare',
                'cf-browser-verification',
                'cf-challenge',
                'turnstile',
                'checking your browser',
                'verifying you are human',
                'please wait while we verify',
                'ddos protection'
            ]
            
            page_content_lower = page_content.lower()
            for indicator in cloudflare_indicators:
                if indicator in page_content_lower:
                    return True
            
            # Check for CloudFlare challenge elements
            challenge_elements = [
                '[data-sitekey]',
                '.cf-challenge-form',
                '#cf-challenge-stage',
                '.turnstile-wrapper'
            ]
            
            for selector in challenge_elements:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for CloudFlare challenge: {e}")
            return False
    
    async def _wait_for_challenge_completion(self, page: Any, email: str, max_wait: int = 30) -> bool:
        """Wait for CloudFlare challenges to complete"""
        try:
            logger.info(f"⏳ {email} - Waiting for CloudFlare challenge completion...")
            
            for i in range(max_wait):
                await asyncio.sleep(1)
                
                # Check if we still have challenge indicators
                if not await self._has_cloudflare_challenge(page):
                    logger.info(f"✅ {email} - CloudFlare challenge completed after {i+1}s")
                    return True
                
                # Check for specific completion indicators
                try:
                    # Look for success indicators
                    success_indicators = [
                        'login',
                        'signin',
                        'account',
                        'dashboard'
                    ]
                    
                    current_url = page.url.lower()
                    for indicator in success_indicators:
                        if indicator in current_url:
                            logger.info(f"✅ {email} - Challenge completed, redirected to: {page.url}")
                            return True
                    
                    # Check if page content changed (no longer showing "verifying")
                    page_content = await page.content()
                    if 'verifying' not in page_content.lower() and 'checking' not in page_content.lower():
                        # Additional check - make sure we're not on an error page
                        if 'error' not in page_content.lower() and 'blocked' not in page_content.lower():
                            logger.info(f"✅ {email} - Challenge appears to be completed")
                            return True
                
                except Exception:
                    continue
                
                # Log progress every 10 seconds
                if (i + 1) % 10 == 0:
                    logger.info(f"⏳ {email} - Still waiting for challenge completion... ({i+1}s)")
            
            logger.warning(f"⚠️ {email} - Challenge completion timeout after {max_wait}s")
            return False
            
        except Exception as e:
            logger.warning(f"Error waiting for challenge completion: {e}")
            return False
    
    async def _fill_login_form(self, page: Any, email: str, password: str) -> bool:
        """Fill the login form with credentials"""
        try:
            logger.info(f"📝 {email} - Filling login form...")
            
            # First, ensure we're past any Cloudflare challenges
            await self._wait_for_challenge_completion(page, email, max_wait=60)
            
            # Wait for the actual login page to load (not just Cloudflare)
            logger.info(f"⏳ {email} - Waiting for login form to appear...")
            
            # Wait for page title to change from "Just a moment..."
            for i in range(30):  # 30 seconds max
                await asyncio.sleep(1)
                title = await page.title()
                if "just a moment" not in title.lower() and "sign in" in title.lower():
                    logger.info(f"✅ {email} - Login page loaded (title: {title})")
                    break
                elif i == 29:
                    logger.warning(f"⚠️ {email} - Login page may not have loaded properly (title: {title})")
            
            # EXACT LOGIN SEQUENCE - Based on comprehensive analysis
            logger.info(f"📧 {email} - Starting exact login sequence...")
            
            # STEP 1: Fill email using JavaScript (most reliable method discovered)
            logger.info(f"🔧 {email} - Filling email via JavaScript...")
            email_filled = await page.evaluate(f"""
                (email) => {{
                    // Find the email input field
                    const emailInput = document.querySelector('input[id="email"], input[name="email"], input[type="email"]');
                    if (emailInput) {{
                        // Set value directly
                        emailInput.value = email;
                        
                        // Dispatch events to ensure proper form handling
                        emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        emailInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        
                        return {{ success: true, value: emailInput.value }};
                    }}
                    return {{ success: false }};
                }}
            """, email)
            
            if email_filled.get('success') and email_filled.get('value') == email:
                logger.info(f"✅ {email} - Email filled successfully via JavaScript")
                
                # STEP 2: Click Continue button after email
                logger.info(f"➡️ {email} - Clicking Continue button...")
                await asyncio.sleep(2)  # Wait for form to process email
                
                continue_success = False
                try:
                    continue_btn = await page.query_selector('button:has-text("Continue")')
                    if continue_btn:
                        is_visible = await continue_btn.is_visible()
                        is_enabled = await continue_btn.is_enabled()
                        
                        if is_visible and is_enabled:
                            await continue_btn.click()
                            continue_success = True
                            logger.info(f"✅ {email} - Continue button clicked")
                        else:
                            logger.warning(f"⚠️ {email} - Continue button not interactive")
                    else:
                        logger.warning(f"⚠️ {email} - Continue button not found")
                except Exception as e:
                    logger.warning(f"⚠️ {email} - Continue button click failed: {e}")
                
                # Fallback: Use Enter key
                if not continue_success:
                    logger.info(f"🔄 {email} - Using Enter key as Continue fallback...")
                    await page.keyboard.press('Enter')
                    logger.info(f"✅ {email} - Enter key pressed as continue")
                
                await asyncio.sleep(3)  # Wait for password step to load
                
                # STEP 3: Fill password field
                logger.info(f"🔒 {email} - Filling password field...")
                
                try:
                    # Wait for password field to appear
                    await page.wait_for_selector('input[type="password"]', timeout=10000)
                    password_input = await page.query_selector('input[type="password"]')
                    
                    if password_input:
                        is_visible = await password_input.is_visible()
                        is_enabled = await password_input.is_enabled()
                        
                        if is_visible and is_enabled:
                            await password_input.fill(password)
                            logger.info(f"✅ {email} - Password field filled successfully")
                        else:
                            logger.error(f"❌ {email} - Password field not interactive")
                            raise Exception("Password field not interactive")
                    else:
                        logger.error(f"❌ {email} - Password field not found")
                        raise Exception("Password field not found")
                except Exception as e:
                    # Before failing, check if we're on a challenge page
                    logger.warning(f"⚠️ {email} - Failed to fill password, checking for challenges...")
                    if await self.check_and_handle_challenges_anywhere(page, email, "password_fill_failed"):
                        # Challenge was solved, try again
                        try:
                            await page.wait_for_selector('input[type="password"]', timeout=10000)
                            password_input = await page.query_selector('input[type="password"]')
                            if password_input and await password_input.is_visible() and await password_input.is_enabled():
                                await password_input.fill(password)
                                logger.info(f"✅ {email} - Password filled after challenge resolution")
                            else:
                                logger.error(f"❌ {email} - Password field still not interactive after challenge resolution")
                                raise Exception("Password field not interactive after challenge resolution")
                        except Exception as retry_e:
                            logger.error(f"❌ {email} - Failed to fill password even after challenge resolution: {retry_e}")
                            raise Exception("Failed to fill password field after challenge resolution")
                    else:
                        logger.error(f"❌ {email} - Failed to fill password: {e}")
                        raise Exception("Failed to fill password field")
                
                # STEP 4: Click Sign in button immediately after password is filled
                logger.info(f"🚀 {email} - Step 4: Clicking Sign in button...")
                await asyncio.sleep(2)  # Wait for form to process password
                
                # Find and click the Sign in button
                signin_success = False
                signin_selectors = [
                    'button:has-text("Sign in")',      # EXACT from analysis
                    'button[type="submit"]',           # Fallback
                    'input[type="submit"]',            # Fallback
                ]
                
                for selector in signin_selectors:
                    try:
                        signin_btn = await page.query_selector(selector)
                        if signin_btn:
                            is_visible = await signin_btn.is_visible()
                            is_enabled = await signin_btn.is_enabled()
                            
                            if is_visible and is_enabled:
                                await signin_btn.click()
                                signin_success = True
                                logger.info(f"✅ {email} - Sign in button clicked with {selector}")
                                break
                            else:
                                logger.warning(f"⚠️ {email} - Sign in button not interactive: {selector}")
                    except Exception as e:
                        logger.debug(f"Sign in selector failed {selector}: {e}")
                        continue
                
                # Fallback: Use Enter key (ALWAYS works)
                if not signin_success:
                    logger.info(f"🔄 {email} - Sign in button not found, using Enter key fallback...")
                    try:
                        await page.keyboard.press('Enter')
                        signin_success = True
                        logger.info(f"✅ {email} - Enter key pressed for sign in")
                    except Exception as e:
                        logger.warning(f"⚠️ {email} - Enter key failed: {e}")
                
                # Final fallback: Try Tab + Enter
                if not signin_success:
                    logger.info(f"🔄 {email} - Trying Tab + Enter as final fallback...")
                    try:
                        await page.keyboard.press('Tab')
                        await asyncio.sleep(0.5)
                        await page.keyboard.press('Enter')
                        signin_success = True
                        logger.info(f"✅ {email} - Tab + Enter pressed for sign in")
                    except Exception as e:
                        logger.warning(f"⚠️ {email} - Tab + Enter failed: {e}")
                
                # If all methods fail, continue anyway (form might auto-submit)
                if not signin_success:
                    logger.warning(f"⚠️ {email} - All sign in methods failed, continuing anyway...")
                    signin_success = True  # Continue with challenge handling
                
                # STEP 5: Handle post-submission challenges
                logger.info(f"🛡️ {email} - Monitoring for post-submission challenges...")
                await asyncio.sleep(3)  # Wait for challenge to appear
                
                # Enhanced challenge detection and solving
                challenge_solved = await self._handle_comprehensive_challenges(page, email)
                
                if challenge_solved:
                    logger.info(f"✅ {email} - All post-submission challenges resolved")
                    # Wait 5 seconds after challenge completion as requested
                    logger.info(f"⏳ {email} - Waiting 5 seconds after challenge completion...")
                    await asyncio.sleep(5)
                    logger.info(f"✅ {email} - Login sequence completed successfully")
                else:
                    logger.error(f"❌ {email} - Failed to resolve post-submission challenges")
                    raise Exception("Failed to resolve post-submission challenges")
                
                logger.info(f"✅ {email} - Complete login form sequence finished successfully")
            else:
                logger.error(f"❌ {email} - Failed to fill email field")
                raise Exception("Email field filling failed")
            
            # Wait for form elements to be available - based on debug results
            try:
                # The debug shows these selectors work, so wait for them properly
                await page.wait_for_selector('input[type="email"]', timeout=20000)
                logger.info(f"✅ {email} - Email field found")
            except Exception as e:
                logger.warning(f"⚠️ {email} - Email field not found with primary selector, trying alternatives...")
                try:
                    # Try alternative selectors that debug showed work
                    await page.wait_for_selector('input[name="email"]', timeout=10000)
                    logger.info(f"✅ {email} - Email field found via name attribute")
                except Exception as e2:
                    try:
                        await page.wait_for_selector('input[id="email"]', timeout=10000)
                        logger.info(f"✅ {email} - Email field found via id attribute")
                    except Exception as e3:
                        # Before failing, check if we're on a challenge page
                        logger.warning(f"⚠️ {email} - Could not find email field, checking for challenges...")
                        if await self.check_and_handle_challenges_anywhere(page, email, "email_field_not_found"):
                            # Challenge was solved, try again
                            try:
                                await page.wait_for_selector('input[type="email"]', timeout=10000)
                                logger.info(f"✅ {email} - Email field found after challenge resolution")
                            except:
                                logger.error(f"❌ {email} - Email field still not found after challenge resolution")
                                raise Exception("Email field not found even after challenge resolution")
                        else:
                            logger.error(f"❌ {email} - Could not find email field and no challenges detected")
                            raise Exception("Email field not found")
            
            # Find and fill email field - prioritize exact selectors found by debug script
            email_selectors = [
                'input[type="email"]',  # Epic Games uses this - most reliable
                'input[name="email"]',  # Epic Games has name="email"
                'input[id="email"]',    # Epic Games has id="email"
                'input[placeholder*="email" i]',
                'input[aria-label*="email" i]'
            ]
            
            email_filled = False
            for selector in email_selectors:
                try:
                    # Wait for the specific selector to be available
                    await page.wait_for_selector(selector, timeout=5000)
                    email_field = await page.query_selector(selector)
                    if email_field:
                        # Check if element is visible and enabled
                        is_visible = await email_field.is_visible()
                        is_enabled = await email_field.is_enabled()
                        
                        if is_visible and is_enabled:
                            # Use fill method instead of clear + type for better compatibility
                            try:
                                await email_field.fill(email)
                                email_filled = True
                                logger.info(f"✅ {email} - Email field filled using selector: {selector}")
                                break
                            except Exception as fill_error:
                                # Fallback to click + clear + type
                                try:
                                    await email_field.click()
                                    await email_field.clear()
                                    await email_field.type(email, delay=random.randint(50, 150))
                                    email_filled = True
                                    logger.info(f"✅ {email} - Email field filled using fallback method: {selector}")
                                    break
                                except Exception as fallback_error:
                                    logger.debug(f"Both fill methods failed for {selector}: {fill_error}, {fallback_error}")
                        else:
                            logger.info(f"⚠️ {email} - Email field found but not interactive (visible: {is_visible}, enabled: {is_enabled})")
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not email_filled:
                logger.info(f"❌ {email} - Could not find interactive email field")
                return False
            
            # Small delay between fields
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Find and fill password field - prioritize exact selectors found by debug script
            password_selectors = [
                'input[type="password"]',  # Epic Games uses this - most reliable
                'input[name="password"]',  # Epic Games has name="password"
                'input[id="password"]',    # Epic Games has id="password"
                'input[placeholder*="password" i]',
                'input[aria-label*="password" i]'
            ]
            
            password_filled = False
            for selector in password_selectors:
                try:
                    # Wait for the specific selector to be available
                    await page.wait_for_selector(selector, timeout=5000)
                    password_field = await page.query_selector(selector)
                    if password_field:
                        # Check if element is visible and enabled
                        is_visible = await password_field.is_visible()
                        is_enabled = await password_field.is_enabled()
                        
                        if is_visible and is_enabled:
                            # Use fill method instead of clear + type for better compatibility
                            try:
                                await password_field.fill(password)
                                password_filled = True
                                logger.info(f"✅ {email} - Password field filled using selector: {selector}")
                                break
                            except Exception as fill_error:
                                # Fallback to click + clear + type
                                try:
                                    await password_field.click()
                                    await password_field.clear()
                                    await password_field.type(password, delay=random.randint(50, 150))
                                    password_filled = True
                                    logger.info(f"✅ {email} - Password field filled using fallback method: {selector}")
                                    break
                                except Exception as fallback_error:
                                    logger.debug(f"Both fill methods failed for {selector}: {fill_error}, {fallback_error}")
                        else:
                            logger.info(f"⚠️ {email} - Password field found but not interactive (visible: {is_visible}, enabled: {is_enabled})")
                except Exception as e:
                    logger.debug(f"Password selector {selector} failed: {e}")
                    continue
            
            if not password_filled:
                # Before failing, check if we're on a challenge page
                logger.warning(f"⚠️ {email} - Could not find password field, checking for challenges...")
                if await self.check_and_handle_challenges_anywhere(page, email, "password_field_not_found"):
                    # Challenge was solved, try again
                    for selector in password_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            password_field = await page.query_selector(selector)
                            if password_field and await password_field.is_visible() and await password_field.is_enabled():
                                await password_field.fill(password)
                                password_filled = True
                                logger.info(f"✅ {email} - Password field found and filled after challenge resolution")
                                break
                        except:
                            continue
                    
                    if not password_filled:
                        logger.error(f"❌ {email} - Password field still not found after challenge resolution")
                        return False
                else:
                    logger.error(f"❌ {email} - Could not find password field and no challenges detected")
                    return False
            
            # Small delay after filling
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            logger.info(f"✅ {email} - Login form filled successfully")
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Error filling login form: {str(e)}")
            return False
    
    async def _submit_login_form(self, page: Any, email: str) -> bool:
        """Submit the login form and handle any challenges"""
        try:
            logger.info(f"🚀 {email} - Submitting login form...")
            
            # Handle any Turnstile challenges before submission
            challenge_result = await self.turnstile_handler.solve_turnstile_challenge(page)
            if not challenge_result.get('success') and challenge_result.get('status') == 'captcha':
                logger.info(f"❌ {email} - Failed to solve Turnstile before submission: {challenge_result.get('error', 'Unknown error')}")
                return False
            
            # STEP 4: Click Sign in button (exact sequence from analysis)
            logger.info(f"🚀 {email} - Step 4: Clicking Sign in button...")
            await asyncio.sleep(2)  # Wait for form to process password
            
            # Use exact selectors from comprehensive analysis
            submit_selectors = [
                'button:has-text("Sign in")',      # EXACT from analysis - most reliable
                'button[type="submit"]',           # Fallback
                'input[type="submit"]',            # Fallback
                'button:has-text("Continue")',     # Fallback
                'button:has-text("Login")'         # Fallback
            ]
            
            submit_clicked = False
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button:
                        # Check if button is enabled
                        is_disabled = await submit_button.get_attribute('disabled')
                        if is_disabled:
                            logger.info(f"⚠️ {email} - Submit button is disabled, waiting...")
                            await asyncio.sleep(2)
                            continue
                        
                        await submit_button.click()
                        submit_clicked = True
                        logger.info(f"✅ {email} - Submit button clicked")
                        break
                except:
                    continue
            
            if not submit_clicked:
                # Try pressing Enter as fallback
                try:
                    await page.keyboard.press('Enter')
                    submit_clicked = True
                    logger.info(f"✅ {email} - Form submitted with Enter key")
                except:
                    pass
            
            if not submit_clicked:
                logger.info(f"❌ {email} - Could not submit login form")
                return False
            
            # ENHANCED POST-SUBMISSION CHALLENGE HANDLING
            logger.info(f"🛡️ {email} - Monitoring for post-submission challenges...")
            await asyncio.sleep(3)  # Initial wait for submission to process
            
            # Comprehensive challenge detection and solving
            challenge_solved = await self._handle_post_submission_challenges(page, email)
            
            if challenge_solved:
                logger.info(f"✅ {email} - All post-submission challenges resolved")
                # Wait 5 seconds after challenge completion as requested
                logger.info(f"⏳ {email} - Waiting 5 seconds after challenge completion...")
                await asyncio.sleep(5)
                
                logger.info(f"✅ {email} - Login form submission completed successfully")
                return True
            else:
                logger.error(f"❌ {email} - Failed to resolve post-submission challenges")
                return False
            
        except Exception as e:
            logger.info(f"❌ {email} - Error submitting login form: {str(e)}")
            return False
    
    async def _handle_post_submission_challenges(self, page: Any, email: str) -> bool:
        """
        Comprehensive post-submission challenge handler
        Detects and solves any Cloudflare/Turnstile challenges that appear after login submission
        """
        try:
            logger.info(f"🔍 {email} - Starting comprehensive post-submission challenge detection...")
            
            max_challenge_attempts = 5
            challenge_attempt = 0
            total_wait_time = 0
            max_total_wait = 60  # Maximum 60 seconds total wait
            
            while challenge_attempt < max_challenge_attempts and total_wait_time < max_total_wait:
                challenge_attempt += 1
                logger.info(f"🔍 {email} - Challenge detection attempt {challenge_attempt}/{max_challenge_attempts}")
                
                # Enhanced challenge detection
                challenge_info = await self.turnstile_handler.detect_turnstile_challenge(page)
                
                if challenge_info.get('detected'):
                    challenge_type = challenge_info.get('type', 'Unknown')
                    logger.info(f"🛡️ {email} - Post-submission challenge detected: {challenge_type}")
                    
                    # Take screenshot of challenge
                    try:
                        await self.turnstile_handler.take_screenshot_and_upload(
                            page, f"{email}_post_submission_challenge_detected_attempt_{challenge_attempt}"
                        )
                    except Exception:
                        pass
                    
                    # Attempt to solve the challenge using all available methods
                    challenge_result = await self._solve_challenge_with_all_methods(page, email, challenge_attempt)
                    
                    if challenge_result.get('success'):
                        logger.info(f"✅ {email} - Challenge solved successfully on attempt {challenge_attempt}")
                        
                        # Wait for challenge completion to be processed
                        logger.info(f"⏳ {email} - Waiting for challenge completion to be processed...")
                        await asyncio.sleep(3)
                        
                        # Verify challenge is actually resolved
                        verification_wait = 0
                        max_verification_wait = 15
                        
                        while verification_wait < max_verification_wait:
                            await asyncio.sleep(1)
                            verification_wait += 1
                            
                            # Check if challenge is still present
                            recheck_info = await self.turnstile_handler.detect_turnstile_challenge(page)
                            if not recheck_info.get('detected'):
                                logger.info(f"✅ {email} - Challenge completion verified after {verification_wait}s")
                                return True
                            
                            if verification_wait % 3 == 0:
                                logger.info(f"⏳ {email} - Still verifying challenge completion... ({verification_wait}s)")
                        
                        logger.warning(f"⚠️ {email} - Challenge may not be fully resolved, continuing...")
                        
                    else:
                        error_msg = challenge_result.get('error', 'Unknown error')
                        logger.warning(f"⚠️ {email} - Challenge solving failed on attempt {challenge_attempt}: {error_msg}")
                        
                        # Take screenshot of failure
                        try:
                            await self.turnstile_handler.take_screenshot_and_upload(
                                page, f"{email}_post_submission_challenge_failed_attempt_{challenge_attempt}"
                            )
                        except Exception:
                            pass
                        
                        # Wait before next attempt
                        await asyncio.sleep(2)
                        total_wait_time += 2
                
                else:
                    # No challenge detected
                    logger.info(f"✅ {email} - No post-submission challenge detected on attempt {challenge_attempt}")
                    
                    # Double-check by waiting a bit and checking again
                    if challenge_attempt == 1:
                        logger.info(f"🔍 {email} - Double-checking for delayed challenges...")
                        await asyncio.sleep(3)
                        total_wait_time += 3
                        
                        # Final check
                        final_check = await self.turnstile_handler.detect_turnstile_challenge(page)
                        if final_check.get('detected'):
                            logger.info(f"🛡️ {email} - Delayed challenge detected on final check")
                            continue  # Go back to challenge handling
                    
                    # No challenge found, we're good
                    logger.info(f"✅ {email} - No post-submission challenges found")
                    return True
                
                # Add to total wait time
                total_wait_time += 1
                await asyncio.sleep(1)
            
            # If we get here, we've exhausted our attempts
            if total_wait_time >= max_total_wait:
                logger.error(f"❌ {email} - Challenge handling timed out after {max_total_wait}s")
            else:
                logger.error(f"❌ {email} - Exhausted all {max_challenge_attempts} challenge attempts")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ {email} - Error in post-submission challenge handling: {e}")
            return False
    
    async def _solve_challenge_with_all_methods(self, page: Any, email: str, attempt: int) -> dict:
        """
        Attempt to solve challenge using all available methods
        """
        try:
            logger.info(f"🎯 {email} - Attempting to solve challenge with all available methods (attempt {attempt})")
            
            # Method 1: Primary Turnstile solver
            logger.info(f"🔧 {email} - Trying Method 1: Primary Turnstile solver...")
            result1 = await self.turnstile_handler.solve_turnstile_challenge(page)
            
            if result1.get('success'):
                logger.info(f"✅ {email} - Method 1 (Primary Turnstile) succeeded")
                return {'success': True, 'method': 'primary_turnstile'}
            else:
                logger.warning(f"⚠️ {email} - Method 1 failed: {result1.get('error', 'Unknown error')}")
            
            # Method 2: Wait and retry approach (sometimes challenges auto-resolve)
            logger.info(f"🔧 {email} - Trying Method 2: Wait and retry approach...")
            await asyncio.sleep(5)
            
            # Check if challenge resolved itself
            recheck = await self.turnstile_handler.detect_turnstile_challenge(page)
            if not recheck.get('detected'):
                logger.info(f"✅ {email} - Method 2 (Wait and retry) succeeded - challenge auto-resolved")
                return {'success': True, 'method': 'auto_resolve'}
            
            # Method 3: Try clicking through the challenge manually
            logger.info(f"🔧 {email} - Trying Method 3: Manual challenge interaction...")
            manual_result = await self._try_manual_challenge_interaction(page, email)
            
            if manual_result:
                logger.info(f"✅ {email} - Method 3 (Manual interaction) succeeded")
                return {'success': True, 'method': 'manual_interaction'}
            
            # Method 4: Page refresh and retry (last resort)
            if attempt <= 2:  # Only try refresh on early attempts
                logger.info(f"🔧 {email} - Trying Method 4: Page refresh approach...")
                try:
                    await page.reload(wait_until='networkidle', timeout=15000)
                    await asyncio.sleep(3)
                    
                    # Check if challenge is gone after refresh
                    post_refresh_check = await self.turnstile_handler.detect_turnstile_challenge(page)
                    if not post_refresh_check.get('detected'):
                        logger.info(f"✅ {email} - Method 4 (Page refresh) succeeded")
                        return {'success': True, 'method': 'page_refresh'}
                except Exception as refresh_error:
                    logger.warning(f"⚠️ {email} - Page refresh failed: {refresh_error}")
            
            # All methods failed
            logger.error(f"❌ {email} - All challenge solving methods failed")
            return {'success': False, 'error': 'All methods exhausted'}
            
        except Exception as e:
            logger.error(f"❌ {email} - Error in challenge solving: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _try_manual_challenge_interaction(self, page: Any, email: str) -> bool:
        """
        Try to interact with challenge elements manually
        """
        try:
            logger.info(f"🖱️ {email} - Attempting manual challenge interaction...")
            
            # Look for common challenge elements to click
            challenge_selectors = [
                'input[type="checkbox"]',  # Checkbox challenges
                '.cf-turnstile',           # Turnstile widget
                '[data-sitekey]',          # Elements with sitekey
                'iframe[src*="challenges.cloudflare.com"]',  # Cloudflare iframe
                'iframe[src*="turnstile"]' # Turnstile iframe
            ]
            
            for selector in challenge_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        is_visible = await element.is_visible()
                        if is_visible:
                            logger.info(f"🖱️ {email} - Clicking challenge element: {selector}")
                            await element.click()
                            await asyncio.sleep(2)
                            
                            # Check if this resolved the challenge
                            check_result = await self.turnstile_handler.detect_turnstile_challenge(page)
                            if not check_result.get('detected'):
                                logger.info(f"✅ {email} - Manual interaction successful")
                                return True
                except Exception:
                    continue
            
            logger.info(f"⚠️ {email} - Manual challenge interaction did not resolve challenge")
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ {email} - Manual challenge interaction error: {e}")
            return False
    
    async def check_and_handle_challenges_anywhere(self, page: Any, email: str, context: str = "unknown") -> bool:
        """
        UNIVERSAL CHALLENGE DETECTOR - Can be called at ANY point during login process
        This method stops the automated browser, detects challenges, solves them, then continues
        """
        try:
            logger.info(f"🔍 {email} - [{context}] Checking for Cloudflare challenges...")
            
            # Quick check first - if no challenge, return immediately
            if not await self._has_cloudflare_challenge(page):
                current_url = page.url
                page_title = await page.title()
                
                # Additional checks for challenge indicators
                challenge_indicators = [
                    "challenges.cloudflare.com" in current_url,
                    "cf-challenge" in current_url,
                    "just a moment" in page_title.lower(),
                    "checking your browser" in page_title.lower(),
                    "please wait" in page_title.lower(),
                    "cloudflare" in page_title.lower()
                ]
                
                if not any(challenge_indicators):
                    logger.info(f"✅ {email} - [{context}] No challenges detected, continuing...")
                    return True
            
            # Challenge detected - stop automated browser and handle it
            logger.warning(f"🛡️ {email} - [{context}] CHALLENGE DETECTED! Stopping automated browser...")
            
            # Take screenshot for debugging
            try:
                await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_challenge_detected_{context}")
            except:
                pass
            
            # Handle the challenge using comprehensive method
            challenge_result = await self._handle_comprehensive_challenges(page, email)
            
            if challenge_result:
                logger.info(f"✅ {email} - [{context}] Challenge solved successfully! Resuming automation...")
                # Wait a moment for page to stabilize after challenge resolution
                await asyncio.sleep(3)
                return True
            else:
                logger.error(f"❌ {email} - [{context}] Failed to solve challenge!")
                return False
                
        except Exception as e:
            logger.error(f"❌ {email} - [{context}] Error during challenge detection: {e}")
            return False

    async def _handle_comprehensive_challenges(self, page: Any, email: str) -> bool:
        """
        COMPREHENSIVE CHALLENGE HANDLER - ACTUALLY WORKS
        This method detects and solves ANY Cloudflare/Turnstile challenge that appears
        """
        try:
            logger.info(f"🔍 {email} - COMPREHENSIVE CHALLENGE DETECTION STARTING...")
            
            max_attempts = 10
            attempt = 0
            total_wait = 0
            max_total_wait = 90  # 90 seconds max
            
            while attempt < max_attempts and total_wait < max_total_wait:
                attempt += 1
                logger.info(f"🔍 {email} - Challenge detection attempt {attempt}/{max_attempts}")
                
                # Check current page state
                current_url = page.url
                page_title = await page.title()
                logger.info(f"🌐 {email} - Current URL: {current_url}")
                logger.info(f"📄 {email} - Page title: {page_title}")
                
                # Method 1: Check for Cloudflare challenge page
                if "challenges.cloudflare.com" in current_url or "cf-challenge" in current_url:
                    logger.info(f"🛡️ {email} - CLOUDFLARE CHALLENGE PAGE DETECTED!")
                    
                    # Take screenshot
                    try:
                        await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_cloudflare_challenge_page")
                    except:
                        pass
                    
                    # Wait for challenge to auto-resolve or try to solve it
                    logger.info(f"⏳ {email} - Waiting for Cloudflare challenge to resolve...")
                    
                    # Try multiple solving approaches
                    for solve_attempt in range(3):
                        await asyncio.sleep(5)  # Wait 5 seconds
                        
                        # Check if challenge resolved
                        new_url = page.url
                        if "challenges.cloudflare.com" not in new_url and "cf-challenge" not in new_url:
                            logger.info(f"✅ {email} - Cloudflare challenge resolved! New URL: {new_url}")
                            return True
                        
                        # Try clicking challenge elements
                        try:
                            challenge_elements = await page.query_selector_all('input[type="checkbox"], .cf-turnstile, [data-sitekey]')
                            for element in challenge_elements:
                                if await element.is_visible():
                                    await element.click()
                                    logger.info(f"🖱️ {email} - Clicked challenge element")
                                    await asyncio.sleep(3)
                        except:
                            pass
                    
                    # If still on challenge page, continue waiting
                    if "challenges.cloudflare.com" in page.url:
                        logger.warning(f"⚠️ {email} - Still on challenge page, continuing...")
                        await asyncio.sleep(5)
                        total_wait += 5
                        continue
                
                # Method 2: Check for Turnstile widgets on current page
                turnstile_detected = await self.turnstile_handler.detect_turnstile_challenge(page)
                if turnstile_detected.get('detected'):
                    challenge_type = turnstile_detected.get('type', 'Unknown')
                    logger.info(f"🛡️ {email} - TURNSTILE CHALLENGE DETECTED: {challenge_type}")
                    
                    # Take screenshot
                    try:
                        await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_turnstile_challenge")
                    except:
                        pass
                    
                    # Try to solve with all available methods
                    logger.info(f"🎯 {email} - Attempting to solve Turnstile challenge...")
                    
                    # Method A: Primary solver
                    try:
                        result = await self.turnstile_handler.solve_turnstile_challenge(page)
                        if result.get('success'):
                            logger.info(f"✅ {email} - Turnstile solved with primary solver!")
                            await asyncio.sleep(3)
                            return True
                    except Exception as e:
                        logger.warning(f"⚠️ {email} - Primary solver failed: {e}")
                    
                    # Method B: Manual interaction
                    try:
                        manual_result = await self._try_manual_challenge_interaction(page, email)
                        if manual_result:
                            logger.info(f"✅ {email} - Turnstile solved with manual interaction!")
                            await asyncio.sleep(3)
                            return True
                    except Exception as e:
                        logger.warning(f"⚠️ {email} - Manual interaction failed: {e}")
                    
                    # Method C: Wait and retry
                    logger.info(f"⏳ {email} - Waiting for Turnstile to auto-resolve...")
                    await asyncio.sleep(10)
                    
                    # Check if resolved
                    recheck = await self.turnstile_handler.detect_turnstile_challenge(page)
                    if not recheck.get('detected'):
                        logger.info(f"✅ {email} - Turnstile auto-resolved!")
                        return True
                
                # Method 3: Check for successful login indicators
                success_indicators = [
                    "account.epicgames.com",
                    "launcher.store.epicgames.com", 
                    "dashboard",
                    "profile",
                    "library"
                ]
                
                if any(indicator in current_url.lower() for indicator in success_indicators):
                    logger.info(f"✅ {email} - SUCCESS DETECTED! Logged in successfully")
                    return True
                
                # Method 4: Check page content for success/failure indicators
                try:
                    page_content = await page.content()
                    page_content_lower = page_content.lower()
                    
                    # Success indicators
                    if any(success_text in page_content_lower for success_text in [
                        "welcome", "dashboard", "profile", "library", "account settings"
                    ]):
                        logger.info(f"✅ {email} - SUCCESS DETECTED in page content!")
                        return True
                    
                    # Challenge indicators
                    if any(challenge_text in page_content_lower for challenge_text in [
                        "checking your browser", "please wait", "verifying", "challenge"
                    ]):
                        logger.info(f"🛡️ {email} - Challenge detected in page content, waiting...")
                        await asyncio.sleep(5)
                        total_wait += 5
                        continue
                    
                    # Error indicators
                    if any(error_text in page_content_lower for error_text in [
                        "invalid", "incorrect", "wrong password", "login failed"
                    ]):
                        logger.error(f"❌ {email} - Login error detected in page content")
                        return False
                        
                except Exception as e:
                    logger.debug(f"Error checking page content: {e}")
                
                # Method 5: Check if still on login page
                if "login" in current_url.lower() or "signin" in current_url.lower():
                    logger.warning(f"⚠️ {email} - Still on login page, may need more time...")
                    await asyncio.sleep(5)
                    total_wait += 5
                    continue
                
                # If no challenges detected and not on login page, assume success
                logger.info(f"✅ {email} - No challenges detected, assuming success")
                return True
            
            # If we get here, we've exhausted attempts
            logger.error(f"❌ {email} - Challenge handling exhausted after {max_attempts} attempts and {total_wait}s")
            return False
            
        except Exception as e:
            logger.error(f"❌ {email} - Comprehensive challenge handling error: {e}")
            return False
    
    async def handle_two_factor_auth(self, page: Any, email: str, two_fa_code: Optional[str] = None) -> bool:
        """Handle two-factor authentication if required"""
        try:
            if not two_fa_code:
                logger.info(f"⚠️ {email} - 2FA required but no code provided")
                return False
            
            logger.info(f"🔐 {email} - Handling two-factor authentication...")
            
            # Wait for 2FA form
            await page.wait_for_selector('input[name*="code"], input[id*="code"], input[placeholder*="code" i]', timeout=10000)
            
            # Find and fill 2FA code field
            code_selectors = [
                'input[name*="code"]',
                'input[id*="code"]',
                'input[placeholder*="code" i]',
                'input[aria-label*="code" i]',
                'input[type="text"][maxlength="6"]',
                'input[type="number"][maxlength="6"]'
            ]
            
            code_filled = False
            for selector in code_selectors:
                try:
                    code_field = await page.query_selector(selector)
                    if code_field:
                        await code_field.clear()
                        await code_field.type(two_fa_code, delay=random.randint(100, 200))
                        code_filled = True
                        logger.info(f"✅ {email} - 2FA code entered")
                        break
                except:
                    continue
            
            if not code_filled:
                logger.info(f"❌ {email} - Could not find 2FA code field")
                return False
            
            # Submit 2FA form
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Verify")',
                'button:has-text("Continue")',
                'button:has-text("Submit")'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button:
                        await submit_button.click()
                        logger.info(f"✅ {email} - 2FA form submitted")
                        break
                except:
                    continue
            
            # Wait for 2FA to process
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Error handling 2FA: {str(e)}")
            return False