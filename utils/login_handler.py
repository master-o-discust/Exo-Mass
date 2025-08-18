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
            
            # Fill login form
            if not await self._fill_login_form(page, email, password):
                try:
                    await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_fill_form_failed")
                except Exception:
                    pass
                return False, {'error': 'Failed to fill login form'}
            
            # Submit form and handle challenges
            if not await self._submit_login_form(page, email):
                try:
                    await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_submit_failed")
                except Exception:
                    pass
                return False, {'error': 'Failed to submit login form'}
            
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
            
            # Wait for form elements to be available - use exact selectors from debug script
            await page.wait_for_selector('input[type="email"], input[name="email"], input[id="email"]', timeout=10000)
            
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
                    email_field = await page.query_selector(selector)
                    if email_field:
                        await email_field.clear()
                        await email_field.type(email, delay=random.randint(50, 150))
                        email_filled = True
                        logger.info(f"✅ {email} - Email field filled")
                        break
                except:
                    continue
            
            if not email_filled:
                logger.info(f"❌ {email} - Could not find email field")
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
                    password_field = await page.query_selector(selector)
                    if password_field:
                        await password_field.clear()
                        await password_field.type(password, delay=random.randint(50, 150))
                        password_filled = True
                        logger.info(f"✅ {email} - Password field filled")
                        break
                except:
                    continue
            
            if not password_filled:
                logger.info(f"❌ {email} - Could not find password field")
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
            
            # Find and click submit button - prioritize exact selectors found by debug script
            submit_selectors = [
                'button[type="submit"]',           # Epic Games uses this - most reliable
                'button:has-text("Continue")',     # Epic Games uses "Continue" text - CRITICAL
                'button[id="continue"]',           # Epic Games has id="continue"
                'input[type="submit"]',
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button[id*="login" i]',
                'button[id*="signin" i]',
                '.login-button',
                '.signin-button'
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
            
            # Wait for form submission to process
            await asyncio.sleep(3)
            
            # Handle any post-submission challenges
            challenge_attempts = 0
            max_challenge_attempts = 3
            
            while challenge_attempts < max_challenge_attempts:
                # Check for Turnstile challenges after submission
                challenge_info = await self.turnstile_handler.detect_turnstile_challenge(page)
                if challenge_info.get('detected'):
                    logger.info(f"🔐 {email} - Post-submission Turnstile detected (attempt {challenge_attempts + 1})")
                    
                    challenge_result = await self.turnstile_handler.solve_turnstile_challenge(page)
                    if challenge_result.get('success'):
                        logger.info(f"✅ {email} - Post-submission Turnstile solved")
                        await asyncio.sleep(2)  # Wait for page to process
                    else:
                        logger.info(f"❌ {email} - Failed to solve post-submission Turnstile: {challenge_result.get('error', 'Unknown error')}")
                        try:
                            await self.turnstile_handler.take_screenshot_and_upload(page, f"{email}_post_submission_turnstile_failed")
                        except Exception:
                            pass
                        return False
                    
                    challenge_attempts += 1
                else:
                    # No more challenges, break out of loop
                    break
            
            # Final wait for login to complete
            await asyncio.sleep(2)
            
            logger.info(f"✅ {email} - Login form submission completed")
            return True
            
        except Exception as e:
            logger.info(f"❌ {email} - Error submitting login form: {str(e)}")
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