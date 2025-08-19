"""
Authentication handler for Epic Games accounts
Simple handler that uses the Epic API client for auth codes and account info
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from utils.epic_api_client import EpicAPIClient

logger = logging.getLogger(__name__)

class AccountStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    CAPTCHA = "captcha"
    TWO_FA = "2fa"
    ERROR = "error"

class AuthHandler:
    """Handles authentication and account information extraction"""
    
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        self.epic_client = None
    
    async def __aenter__(self):
        """Initialize Epic API client"""
        self.epic_client = EpicAPIClient(self.user_id)
        return self
    
    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Clean up"""
        pass
    
    async def detect_outcome_and_extract_auth(self, page, email: str) -> Tuple[AccountStatus, Dict[str, Any]]:
        """
        Detect the outcome of a login attempt by analyzing the current page
        """
        try:
            logger.info(f"🔍 {email} - Detecting login outcome...")
            
            # Wait a moment for page to fully load
            await asyncio.sleep(2)
            
            current_url = page.url.lower()
            logger.info(f"📍 {email} - Current URL: {current_url}")
            
            # Check for successful login indicators
            if any(success_indicator in current_url for success_indicator in [
                'epicgames.com/id/account',
                'fortnite.com/account'
            ]):
                logger.info(f"✅ {email} - Login successful, waiting 8 seconds then taking screenshot...")
                
                # Wait 8 seconds as requested
                await asyncio.sleep(8)
                
                # Take screenshot after 8 seconds
                try:
                    from utils.unified_turnstile_handler import create_turnstile_handler
                    turnstile_handler = create_turnstile_handler()
                    screenshot_path = await turnstile_handler.take_screenshot_and_upload(page, f"{email}_successful_login_8s")
                    logger.info(f"📸 {email} - 8-second post-login screenshot taken: {screenshot_path}")
                except Exception as screenshot_error:
                    logger.warning(f"⚠️ {email} - Failed to take 8-second screenshot: {screenshot_error}")

                # Use Epic API client to get auth code and account info
                success, result = await self.epic_client.get_auth_code_and_info(page, email)
                if success:
                    return AccountStatus.VALID, {
                        'auth_code': result.get('auth_code'),
                        'account_info': result.get('account_info'),
                        'login_url': current_url,
                        'epic_data': result,
                        'post_login_screenshot': screenshot_path if 'screenshot_path' in locals() else None
                    }
                else:
                    # Fallback - just mark as valid but with limited info
                    return AccountStatus.VALID, {
                        'account_info': {'isLoggedIn': True, 'email': email},
                        'login_url': current_url,
                        'error': result.get('error', 'API extraction failed'),
                        'post_login_screenshot': screenshot_path if 'screenshot_path' in locals() else None
                    }
            
            # Check for specific error conditions
            page_content = await page.content()
            page_content_lower = page_content.lower()
            
            # Check for captcha
            if any(captcha_indicator in page_content_lower for captcha_indicator in [
                'captcha', 'recaptcha', 'hcaptcha', 'challenge',
                'verify you are human', 'security check'
            ]):
                logger.info(f"🤖 {email} - Captcha detected")
                return AccountStatus.CAPTCHA, {'error': 'Captcha required'}
            
            # Check for 2FA
            if any(twofa_indicator in page_content_lower for twofa_indicator in [
                'two-factor', '2fa', 'authenticator', 'verification code',
                'enter the code', 'security code'
            ]):
                logger.info(f"🔐 {email} - Two-factor authentication required")
                return AccountStatus.TWO_FA, {'error': '2FA required'}
            
            # Check for invalid credentials
            if any(invalid_indicator in page_content_lower for invalid_indicator in [
                'invalid', 'incorrect', 'wrong password', 'login failed',
                'authentication failed', 'credentials are incorrect'
            ]):
                logger.info(f"❌ {email} - Invalid credentials")
                return AccountStatus.INVALID, {'error': 'Invalid credentials'}
            
            # If we're still on login page, assume invalid
            if any(login_indicator in current_url for login_indicator in [
                'login', 'signin', 'id/login'
            ]):
                logger.info(f"❌ {email} - Still on login page, assuming invalid")
                return AccountStatus.INVALID, {'error': 'Login failed - still on login page'}
            
            # Default case - unclear status
            logger.info(f"❓ {email} - Login outcome unclear")
            return AccountStatus.ERROR, {'error': 'Login outcome unclear'}

        except Exception as e:
            logger.info(f"❌ {email} - Error detecting login outcome: {str(e)}")
            return AccountStatus.ERROR, {'error': f'Detection error: {str(e)}'}

    async def get_account_info_from_page(self, page, email: str) -> Dict[str, Any]:
        """
        Get account information using Epic API client
        """
        try:
            logger.info(f"📋 {email} - Getting account information via Epic API...")
            
            # Use Epic API client to get account info
            success, result = await self.epic_client.get_auth_code_and_info(page, email)
            if success:
                return result.get('account_info', {'isLoggedIn': True, 'email': email})
            else:
                return {'error': result.get('error', 'Failed to get account info')}

        except Exception as e:
            logger.info(f"❌ {email} - Error getting account info: {str(e)}")
            return {'error': f'Account info error: {str(e)}'}