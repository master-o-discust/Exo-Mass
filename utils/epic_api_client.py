"""
Epic Games API Client - Simple and Clean
Only uses the two specified API endpoints:
1. epicgames.com/id/api/redirect?clientId=007c0bfe154c4f5396648f013c641dcf&responseType=code
2. fortnite.com/locale/api/accountInfo
"""
import asyncio
import logging
import json
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from utils.dropbox_uploader import DropboxUploader
from config.settings import DROPBOX_ENABLED

logger = logging.getLogger(__name__)

class EpicAPIClient:
    """Simple Epic Games API client using only the two specified endpoints"""
    
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        
    async def get_auth_code_and_info(self, page, email: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get auth code from Epic Games redirect API and account info from Fortnite API
        Takes screenshots and saves everything
        """
        try:
            logger.info(f"🔑 {email} - Getting auth code and account info...")
            
            # Step 1: Get auth code from Epic Games redirect API
            auth_data = await self._get_auth_code(page, email)
            if not auth_data:
                return False, {'error': 'Failed to get auth code'}
            
            # Step 2: Get account info from Fortnite API
            account_info = await self._get_fortnite_account_info(page, email)
            
            # Step 3: Combine all data
            result = {
                'email': email,
                'timestamp': datetime.now().isoformat(),
                'auth_code': auth_data.get('authorizationCode'),
                'redirect_url': auth_data.get('redirectUrl'),
                'exchange_code': auth_data.get('exchangeCode'),
                'sid': auth_data.get('sid'),
                'sso_v2_enabled': auth_data.get('ssoV2Enabled'),
                'account_info': account_info
            }
            
            # Step 4: Save auth code to .txt file
            if self.user_id and auth_data.get('authorizationCode'):
                await self._save_auth_code_to_file(email, auth_data.get('authorizationCode'))
            
            return True, result
            
        except Exception as e:
            logger.error(f"❌ {email} - Error in Epic API client: {e}")
            return False, {'error': str(e)}
    
    async def _get_auth_code(self, page, email: str) -> Optional[Dict[str, Any]]:
        """Get authorization code from Epic Games redirect API"""
        try:
            logger.info(f"🔗 {email} - Accessing Epic Games redirect API...")
            
            # Navigate to the ONLY Epic Games API endpoint we use
            redirect_url = "https://www.epicgames.com/id/api/redirect?clientId=007c0bfe154c4f5396648f013c641dcf&responseType=code"
            
            response = await page.goto(redirect_url, wait_until="networkidle", timeout=15000)
            if not response or response.status != 200:
                logger.warning(f"⚠️ {email} - Epic redirect API returned status: {response.status if response else 'None'}")
                return None
            
            # Take screenshot of Epic API response
            if DROPBOX_ENABLED and self.user_id:
                await self._take_and_upload_screenshot(page, email, "epic_redirect_api")
            
            # Get the JSON response content
            content = await page.content()
            
            # Parse JSON response to extract auth data
            if 'authorizationCode' in content:
                # Extract JSON data from the response
                try:
                    # Look for JSON structure in the content
                    json_match = re.search(r'\{.*"authorizationCode".*\}', content, re.DOTALL)
                    if json_match:
                        json_data = json.loads(json_match.group(0))
                        logger.info(f"✅ {email} - Auth code extracted: {json_data.get('authorizationCode', '')[:20]}...")
                        return json_data
                    
                    # Alternative: extract individual fields
                    auth_code_match = re.search(r'"authorizationCode":"([^"]+)"', content)
                    redirect_url_match = re.search(r'"redirectUrl":"([^"]+)"', content)
                    exchange_code_match = re.search(r'"exchangeCode":"([^"]+)"', content)
                    sid_match = re.search(r'"sid":"([^"]+)"', content)
                    sso_v2_match = re.search(r'"ssoV2Enabled":([^,}]+)', content)
                    
                    if auth_code_match:
                        result = {
                            'authorizationCode': auth_code_match.group(1),
                            'redirectUrl': redirect_url_match.group(1) if redirect_url_match else None,
                            'exchangeCode': exchange_code_match.group(1) if exchange_code_match else None,
                            'sid': sid_match.group(1) if sid_match else None,
                            'ssoV2Enabled': sso_v2_match.group(1).strip() == 'true' if sso_v2_match else None
                        }
                        logger.info(f"✅ {email} - Auth data extracted successfully")
                        return result
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ {email} - JSON parse error: {e}")
            
            logger.warning(f"⚠️ {email} - No auth code found in Epic API response")
            return None
            
        except Exception as e:
            logger.error(f"❌ {email} - Error getting auth code: {e}")
            return None
    
    async def _get_fortnite_account_info(self, page, email: str) -> Dict[str, Any]:
        """Get account info from Fortnite API"""
        try:
            logger.info(f"🎮 {email} - Getting Fortnite account info...")
            
            # Navigate to the ONLY Fortnite API endpoint we use
            fortnite_api_url = "https://www.fortnite.com/locale/api/accountInfo"
            
            response = await page.goto(fortnite_api_url, wait_until="networkidle", timeout=15000)
            if not response or response.status != 200:
                logger.warning(f"⚠️ {email} - Fortnite API returned status: {response.status if response else 'None'}")
                return {'error': f'Fortnite API error: {response.status if response else "No response"}'}
            
            # Take screenshot of Fortnite API response
            if DROPBOX_ENABLED and self.user_id:
                await self._take_and_upload_screenshot(page, email, "fortnite_account_api")
            
            # Get the JSON response content
            content = await page.content()
            
            # Parse JSON response
            try:
                # Look for JSON in the page content
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    account_data = json.loads(json_match.group(0))
                    logger.info(f"✅ {email} - Fortnite account info retrieved")
                    return account_data
                else:
                    logger.warning(f"⚠️ {email} - No JSON found in Fortnite API response")
                    return {'error': 'No JSON data in response'}
                    
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ {email} - Fortnite API JSON parse error: {e}")
                return {'error': f'JSON parse error: {e}'}
            
        except Exception as e:
            logger.error(f"❌ {email} - Error getting Fortnite account info: {e}")
            return {'error': str(e)}
    
    async def _save_auth_code_to_file(self, email: str, auth_code: str):
        """Save auth code to .txt file"""
        try:
            if not auth_code:
                return
                
            # Create filename with timestamp and email
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_email = email.replace('@', '_at_').replace(':', '_').replace('/', '_')
            filename = f'auth_code_{safe_email}_{timestamp}.txt'
            
            # Create file content
            content = f"Email: {email}\n"
            content += f"Auth Code: {auth_code}\n"
            content += f"Timestamp: {datetime.now().isoformat()}\n"
            content += f"Generated by: Epic Games API Client\n"
            
            # Save locally first
            import os
            from config.settings import DATA_DIR
            user_dir = os.path.join(DATA_DIR, str(self.user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            file_path = os.path.join(user_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Upload to Dropbox if enabled
            if DROPBOX_ENABLED:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("auth_codes", str(self.user_id), date_folder, filename)
                
                upload_success = await DropboxUploader.upload_file(file_path, dropbox_path)
                if upload_success:
                    logger.debug(f"Auth code file uploaded: {dropbox_path}")
                else:
                    logger.debug(f"Auth code upload failed: {filename}")
            
            logger.info(f"💾 {email} - Auth code saved to file")
            
        except Exception as e:
            logger.error(f"❌ {email} - Error saving auth code: {e}")
    
    async def _take_and_upload_screenshot(self, page, email: str, api_type: str):
        """Take screenshot and upload to Dropbox"""
        try:
            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_email = email.replace('@', '_at_').replace(':', '_').replace('/', '_')
            screenshot_name = f'{api_type}_{safe_email}_{timestamp}.png'
            
            screenshot_bytes = await page.screenshot(full_page=True)
            
            # Upload to Dropbox
            date_folder = datetime.now().strftime("%Y-%m-%d")
            dropbox_path = DropboxUploader.build_dropbox_path("screenshots", str(self.user_id), date_folder, api_type, screenshot_name)
            
            upload_success = await DropboxUploader.upload_screenshot(screenshot_bytes, dropbox_path)
            if upload_success:
                logger.debug(f"Screenshot uploaded: {dropbox_path}")
            else:
                logger.debug(f"Screenshot upload failed: {screenshot_name}")
                
        except Exception as e:
            logger.error(f"❌ {email} - Error taking/uploading screenshot: {e}")