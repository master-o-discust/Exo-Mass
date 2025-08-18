#!/usr/bin/env python3
"""
BotsForge CloudFlare Solver Launcher
Properly launches the BotsForge app with correct module imports
"""
import sys
import os
import asyncio
from loguru import logger
from dotenv import load_dotenv

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import API key management utility
from utils.api_key_manager import get_or_create_api_key, sync_api_key_to_file

# Import BotsForge components
from solvers.cloudflare_botsforge.source import LOGO
from solvers.cloudflare_botsforge.app_tasker import Tasker
from solvers.cloudflare_botsforge.async_tasker import Tasker as Solver
from solvers.cloudflare_botsforge.browser import BrowserHandler

load_dotenv()

def setup_api_key():
    """Setup or load API key using the centralized API key manager"""
    # Get or create API key (automatically syncs to .env)
    api_key = get_or_create_api_key()
    
    # Also sync to the legacy .api_key file for backward compatibility
    api_key_file = os.path.join(project_root, 'solvers', 'cloudflare_botsforge', '.api_key')
    sync_api_key_to_file(api_key_file)
    
    return api_key

def install_driver():
    """Install webdriver if needed"""
    logger.info("check and installing webdriver...")
    # Webdriver installation logic would go here
    logger.info("check completed")

async def start():
    """Start the BotsForge server"""
    from quart import Quart, request, jsonify
    import hypercorn.asyncio
    from hypercorn.config import Config
    
    app = Quart(__name__)
    
    @app.route('/', methods=['GET'])
    async def index():
        return "BotsForge CloudFlare Solver API"
    
    @app.route('/createTask', methods=['POST'])
    async def create_task():
        data = await request.get_json()
        logger.info(f"Got new task: {data}")
        
        client_key = data.get('clientKey')
        task = data.get('task', {})
        
        # Validate client key
        if client_key != setup_api_key():
            response = {
                'errorId': 1,
                'errorDescription': 'Wrong clientKey',
                'status': 'error'
            }
            logger.info(f"taskId: None, response: {response}")
            return jsonify(response)
        
        # Process task
        result = Tasker.add_task(data)
        if result.status == 'idle':
            return jsonify({
                'errorId': 0,
                'taskId': result.taskId,
                'status': 'ready'
            })
        else:
            return jsonify({
                'errorId': result.errorId,
                'errorDescription': result.errorDescription,
                'status': result.status
            })
    
    @app.route('/getTaskResult', methods=['POST'])
    async def get_task_result_post():
        """POST endpoint for getting task results (matches unified handler expectations)"""
        try:
            data = await request.get_json()
            client_key = data.get('clientKey')
            task_id = data.get('taskId')
            
            if not client_key or not task_id:
                return jsonify({
                    'errorId': 1,
                    'errorDescription': 'Missing clientKey or taskId',
                    'status': 'error'
                })
            
            # Create payload for get_result method
            from solvers.cloudflare_botsforge.models import CaptchaGetTaskPayload
            payload = CaptchaGetTaskPayload(
                clientKey=client_key,
                taskId=task_id
            )
            result = Tasker.get_result(payload)
            
            # Convert result to dict for JSON response
            if hasattr(result, '__dict__'):
                result_dict = {
                    'errorId': getattr(result, 'errorId', 0),
                    'status': getattr(result, 'status', 'processing'),
                    'taskId': getattr(result, 'taskId', task_id)
                }
                if hasattr(result, 'errorDescription'):
                    result_dict['errorDescription'] = result.errorDescription
                if hasattr(result, 'solution'):
                    result_dict['solution'] = result.solution
                return jsonify(result_dict)
            else:
                return jsonify({
                    'errorId': 0,
                    'status': 'processing',
                    'taskId': task_id
                })
        except Exception as e:
            logger.error(f"Error in get_task_result_post: {e}")
            return jsonify({
                'errorId': 1,
                'errorDescription': str(e),
                'status': 'error'
            })

    @app.route('/getTaskResult/<task_id>', methods=['GET'])
    async def get_task_result_get(task_id):
        """GET endpoint for getting task results (legacy support)"""
        # Create payload for get_result method
        from solvers.cloudflare_botsforge.models import CaptchaGetTaskPayload
        payload = CaptchaGetTaskPayload(
            clientKey=setup_api_key(),
            taskId=task_id
        )
        result = Tasker.get_result(payload)
        
        # Convert result to dict for JSON response
        if hasattr(result, '__dict__'):
            result_dict = {
                'errorId': getattr(result, 'errorId', 0),
                'status': getattr(result, 'status', 'processing'),
                'taskId': getattr(result, 'taskId', task_id)
            }
            if hasattr(result, 'errorDescription'):
                result_dict['errorDescription'] = result.errorDescription
            if hasattr(result, 'solution'):
                result_dict['solution'] = result.solution
            return jsonify(result_dict)
        else:
            return jsonify({
                'errorId': 0,
                'status': 'processing',
                'taskId': task_id
            })
    
    # Configure and start server
    config = Config()
    config.bind = ["127.0.0.1:5033"]
    config.use_reloader = False
    config.accesslog = None
    
    await hypercorn.asyncio.serve(app, config)

if __name__ == "__main__":
    try:
        print(LOGO)
        print("https://t.me/bots_forge")
        print()
        
        api_key = setup_api_key()
        logger.info(f"🚀 BotsForge server starting with API key: {api_key[:8]}...")
        
        install_driver()
        max_workers = int(os.getenv('max_workers', 1))
        
        solver = Solver(max_workers=max_workers, callback_fn=Tasker.add_result)
        Tasker.solvers['AntiTurnstileTaskProxyLess'] = solver
        
        asyncio.run(start())
    except Exception as er:
        logger.exception(er)
    except KeyboardInterrupt:
        logger.info("🛑 BotsForge server stopped by user")
        pass