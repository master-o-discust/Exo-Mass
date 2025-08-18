# 2.0.0

import os
import sys
import ctypes
import asyncio
import subprocess
import secrets
import string
from pathlib import Path

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from loguru import logger
import hypercorn.asyncio
from hypercorn.config import Config

from .source import LOGO
from .app_tasker import Tasker
from .async_tasker import Tasker as Solver
from .browser import BrowserHandler

load_dotenv()

def generate_api_key(length: int = 32) -> str:
    """Generate a secure API key for BotsForge"""
    alphabet = string.ascii_letters + string.digits + '-_'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def setup_api_key():
    """Auto-generate and configure API key for BotsForge"""
    # Check if API key already exists
    existing_key = os.getenv('API_KEY')
    
    if existing_key and existing_key != 'your_api_key_here' and len(existing_key) > 10:
        logger.info(f"✅ Using existing BotsForge API key: {existing_key[:8]}...")
        return existing_key
    
    # Generate new API key
    new_api_key = generate_api_key()
    logger.info(f"🔑 Generated new BotsForge API key: {new_api_key[:8]}...")
    
    # Update .env file
    env_path = Path('.env')
    if env_path.exists():
        try:
            # Read current .env content
            with open(env_path, 'r') as f:
                content = f.read()
            
            # Replace API_KEY line
            lines = content.split('\n')
            updated_lines = []
            api_key_updated = False
            
            for line in lines:
                if line.startswith('API_KEY='):
                    updated_lines.append(f'API_KEY={new_api_key}')
                    api_key_updated = True
                else:
                    updated_lines.append(line)
            
            # If API_KEY line wasn't found, add it
            if not api_key_updated:
                updated_lines.extend(['', '# BotsForge API Configuration', f'API_KEY={new_api_key}'])
            
            # Write updated content
            with open(env_path, 'w') as f:
                f.write('\n'.join(updated_lines))
            
            logger.info("📝 Updated .env file with new BotsForge API key")
            
        except Exception as e:
            logger.error(f"❌ Error updating .env file: {e}")
    
    # Update environment variable for current session
    os.environ['API_KEY'] = new_api_key
    
    return new_api_key

logger.remove(0)
logger.add(sys.stdout, level=os.getenv('LOG_LEVEL', 'INFO'))

# Инициализация приложения
app = Flask(__name__)

task_queue = asyncio.Queue()


async def worker():
    while True:
        fn, arg = await task_queue.get()
        try:
            asyncio.create_task(fn(arg))
        except Exception as e:
            print(f"Ошибка при запуске задачи: {e}")


# HTTP: Создать задачу
@app.route('/createTask', methods=['POST'])
async def create_task():
    logger.info(f'Got new task: {request.json}')
    response = Tasker.add_task(request.json)
    if response.taskId:
        solver = Tasker.solvers['AntiTurnstileTaskProxyLess']
        # await solver.add_task(Tasker.tasks[response.taskId]['task'])
        await task_queue.put((solver.add_task, Tasker.tasks[response.taskId]['task']))
    logger.info(f'taskId: {response.taskId}, response: {response.json()}')
    return jsonify(response.json()), 200


# HTTP: Получить результат задачи
@app.route('/getTaskResult', methods=['POST'])
async def get_task_result():
    logger.info(f'Task result requested: {request.json}')
    response = Tasker.get_result(request.json)
    data = response.json()
    if data['status'] == 'ready':
        token = data['solution']['token']
        data['solution']['token'] = token[:50] + '.....' + token[-50:]
    logger.info(f'taskId: {response.taskId}, response: {data}')
    return jsonify(response.json()), 200


async def start():
    try:
        asyncio.create_task(worker())
        config = Config()
        config.bind = [f"localhost:{int(os.getenv('PORT', 5033))}"]

        await hypercorn.asyncio.serve(app, config)
    finally:
        await BrowserHandler().close()


def install_driver(env=None):
    # Установит все браузеры, необходимые Playwright
    logger.info('check and installing webdriver...')
    subprocess.run(["patchright", "install", "chromium"], check=True)
    logger.info('check completed')


if __name__ == '__main__':
    try:
        if os.name == 'nt':
            ctypes.windll.kernel32.SetConsoleTitleW('CloudFlare-solver')
        print(LOGO)
        
        # Auto-generate and configure API key
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
        pass
    finally:
        input('press <Enter> to close...')
