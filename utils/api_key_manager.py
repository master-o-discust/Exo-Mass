"""
API Key Management Utility
Ensures API keys are synchronized between .env file and service configurations
"""
import os
import secrets
import string
from loguru import logger

def generate_api_key(length=32):
    """Generate a secure random API key"""
    alphabet = string.ascii_letters + string.digits + '_-'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def update_env_api_key(api_key, env_file_path=None):
    """Update the API_KEY in the .env file"""
    if env_file_path is None:
        # Default to project root .env file
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file_path = os.path.join(project_root, '.env')
    
    if not os.path.exists(env_file_path):
        logger.warning(f"⚠️ .env file not found at {env_file_path}")
        return False
    
    try:
        # Read the current .env file
        with open(env_file_path, 'r') as f:
            lines = f.readlines()
        
        # Update or add the API_KEY line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('API_KEY='):
                lines[i] = f'API_KEY={api_key}\n'
                updated = True
                break
        
        # If API_KEY wasn't found, add it
        if not updated:
            lines.append(f'API_KEY={api_key}\n')
        
        # Write back to .env file
        with open(env_file_path, 'w') as f:
            f.writelines(lines)
        
        logger.info(f"✅ Updated API_KEY in .env file: {api_key[:8]}...")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update .env file: {e}")
        return False

def get_or_create_api_key():
    """Get API key from environment or create a new one"""
    # First try to get API key from environment (.env file)
    api_key = os.getenv('API_KEY')
    if api_key:
        logger.info(f"✅ Using API key from environment: {api_key[:8]}...")
        return api_key
    
    # Generate new API key if not found
    api_key = generate_api_key()
    
    # Update .env file
    if update_env_api_key(api_key):
        logger.info(f"🔑 Generated and saved new API key: {api_key[:8]}...")
    else:
        logger.warning(f"⚠️ Generated new API key but failed to save to .env: {api_key[:8]}...")
    
    return api_key

def sync_api_key_to_file(file_path):
    """Sync the current API key to a specific file"""
    api_key = get_or_create_api_key()
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write API key to file
        with open(file_path, 'w') as f:
            f.write(api_key)
        
        logger.info(f"✅ Synced API key to {file_path}: {api_key[:8]}...")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to sync API key to {file_path}: {e}")
        return False