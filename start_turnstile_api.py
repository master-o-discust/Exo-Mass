#!/usr/bin/env python3
"""
Start Turnstile Solver API Server directly
"""
import asyncio
import sys
import os

# Add the turnstile solver directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'solvers', 'turnstile_solver'))

from api_solver import create_app
import hypercorn.asyncio
from hypercorn.config import Config

async def start_api_server():
    """Start the API server directly without user input"""
    print("Starting Turnstile Solver API Server...")
    print("API server starting on http://localhost:5000")
    print("API documentation available at http://localhost:5000/")
    
    try:
        app = create_app(
            headless=True, 
            useragent=None, 
            debug=False, 
            browser_type="camoufox", 
            thread=2, 
            proxy_support=False
        )
        config = Config()
        config.bind = ["127.0.0.1:5000"]
        await hypercorn.asyncio.serve(app, config)
    except Exception as e:
        print(f"API server failed to start: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(start_api_server())