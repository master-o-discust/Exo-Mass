"""
2Captcha Turnstile Solver
Enhanced turnstile solver using 2captcha.com API service
Supports both standalone captchas and Cloudflare Challenge pages
"""

import asyncio
import aiohttp
import time
import logging
import json
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

@dataclass
class TwoCaptchaResult:
    """Result from 2captcha turnstile solving"""
    success: bool
    token: Optional[str] = None
    user_agent: Optional[str] = None
    error: Optional[str] = None
    task_id: Optional[str] = None
    cost: Optional[str] = None
    solve_time: Optional[float] = None


class TwoCaptchaTurnstileSolver:
    """
    2Captcha Turnstile Solver using the official 2captcha.com API
    
    Supports:
    - TurnstileTaskProxyless (using 2captcha's proxy pool)
    - TurnstileTask (using your own proxies)
    - Standalone captchas
    - Cloudflare Challenge pages with action, data, pagedata parameters
    """
    
    BASE_URL = "https://api.2captcha.com"
    
    def __init__(self, api_key: str, timeout: int = 120):
        """
        Initialize 2captcha solver
        
        Args:
            api_key: Your 2captcha API key
            timeout: Maximum time to wait for solution (seconds)
        """
        self.api_key = api_key
        self.timeout = timeout
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'Content-Type': 'application/json'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _parse_proxy(self, proxy: str) -> Optional[Dict[str, Any]]:
        """
        Parse proxy string into 2captcha format
        
        Supports formats:
        - http://user:pass@host:port
        - socks5://user:pass@host:port
        - host:port:user:pass
        - host:port
        """
        if not proxy:
            return None
        
        try:
            # Handle URL format
            if '://' in proxy:
                parsed = urlparse(proxy)
                proxy_type = parsed.scheme.lower()
                
                # Map proxy types to 2captcha format
                if proxy_type in ['http', 'https']:
                    proxy_type = 'http'
                elif proxy_type == 'socks5':
                    proxy_type = 'socks5'
                elif proxy_type == 'socks4':
                    proxy_type = 'socks4'
                else:
                    logger.warning(f"Unsupported proxy type: {proxy_type}, defaulting to http")
                    proxy_type = 'http'
                
                result = {
                    'proxyType': proxy_type,
                    'proxyAddress': parsed.hostname,
                    'proxyPort': parsed.port or (80 if proxy_type == 'http' else 1080)
                }
                
                if parsed.username and parsed.password:
                    result['proxyLogin'] = parsed.username
                    result['proxyPassword'] = parsed.password
                
                return result
            
            # Handle colon-separated format
            parts = proxy.split(':')
            if len(parts) == 2:
                # host:port
                return {
                    'proxyType': 'http',
                    'proxyAddress': parts[0],
                    'proxyPort': int(parts[1])
                }
            elif len(parts) == 4:
                # host:port:user:pass
                return {
                    'proxyType': 'http',
                    'proxyAddress': parts[0],
                    'proxyPort': int(parts[1]),
                    'proxyLogin': parts[2],
                    'proxyPassword': parts[3]
                }
            else:
                logger.error(f"Invalid proxy format: {proxy}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing proxy {proxy}: {e}")
            return None
    
    async def _create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task using 2captcha createTask API"""
        url = f"{self.BASE_URL}/createTask"
        
        payload = {
            "clientKey": self.api_key,
            "task": task_data
        }
        
        logger.debug(f"Creating 2captcha task: {json.dumps(payload, indent=2)}")
        
        async with self.session.post(url, json=payload) as response:
            result = await response.json()
            
            if result.get('errorId', 0) != 0:
                error_msg = result.get('errorDescription', f"Error ID: {result.get('errorId')}")
                logger.error(f"2captcha createTask error: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            task_id = result.get('taskId')
            if not task_id:
                logger.error("No taskId returned from 2captcha")
                return {'success': False, 'error': 'No taskId returned'}
            
            logger.info(f"2captcha task created successfully: {task_id}")
            return {'success': True, 'taskId': task_id}
    
    async def _get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Get task result using 2captcha getTaskResult API"""
        url = f"{self.BASE_URL}/getTaskResult"
        
        payload = {
            "clientKey": self.api_key,
            "taskId": task_id
        }
        
        async with self.session.post(url, json=payload) as response:
            result = await response.json()
            
            if result.get('errorId', 0) != 0:
                error_msg = result.get('errorDescription', f"Error ID: {result.get('errorId')}")
                return {'success': False, 'error': error_msg}
            
            status = result.get('status')
            if status == 'ready':
                solution = result.get('solution', {})
                return {
                    'success': True,
                    'status': 'ready',
                    'token': solution.get('token'),
                    'userAgent': solution.get('userAgent'),
                    'cost': result.get('cost'),
                    'createTime': result.get('createTime'),
                    'endTime': result.get('endTime'),
                    'solveCount': result.get('solveCount')
                }
            elif status == 'processing':
                return {'success': True, 'status': 'processing'}
            else:
                return {'success': False, 'error': f'Unknown status: {status}'}
    
    async def solve_turnstile(
        self,
        website_url: str,
        website_key: str,
        action: Optional[str] = None,
        data: Optional[str] = None,
        pagedata: Optional[str] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TwoCaptchaResult:
        """
        Solve Turnstile captcha using 2captcha service
        
        Args:
            website_url: The full URL where the captcha is loaded
            website_key: Turnstile sitekey from data-sitekey attribute
            action: Action parameter for Cloudflare Challenge pages
            data: cData parameter for Cloudflare Challenge pages  
            pagedata: chlPageData parameter for Cloudflare Challenge pages
            proxy: Proxy string (optional, if not provided uses TurnstileTaskProxyless)
            user_agent: User agent string (optional)
        
        Returns:
            TwoCaptchaResult with solution or error
        """
        start_time = time.time()
        
        try:
            # Determine task type based on proxy availability
            if proxy:
                proxy_config = self._parse_proxy(proxy)
                if not proxy_config:
                    return TwoCaptchaResult(
                        success=False,
                        error="Invalid proxy format"
                    )
                
                task_data = {
                    "type": "TurnstileTask",
                    "websiteURL": website_url,
                    "websiteKey": website_key,
                    **proxy_config
                }
                logger.info(f"Using TurnstileTask with proxy: {proxy_config['proxyAddress']}:{proxy_config['proxyPort']}")
            else:
                task_data = {
                    "type": "TurnstileTaskProxyless", 
                    "websiteURL": website_url,
                    "websiteKey": website_key
                }
                logger.info("Using TurnstileTaskProxyless (2captcha's proxy pool)")
            
            # Add Cloudflare Challenge page parameters if provided
            if action:
                task_data["action"] = action
                logger.debug(f"Added action parameter: {action}")
            
            if data:
                task_data["data"] = data
                logger.debug(f"Added data parameter: {data}")
            
            if pagedata:
                task_data["pagedata"] = pagedata
                logger.debug(f"Added pagedata parameter: {pagedata}")
            
            # Create task
            create_result = await self._create_task(task_data)
            if not create_result['success']:
                return TwoCaptchaResult(
                    success=False,
                    error=create_result['error']
                )
            
            task_id = create_result['taskId']
            logger.info(f"Waiting for 2captcha solution for task: {task_id}")
            
            # Poll for result
            poll_start = time.time()
            while time.time() - poll_start < self.timeout:
                await asyncio.sleep(5)  # Wait 5 seconds between polls
                
                result = await self._get_task_result(task_id)
                if not result['success']:
                    return TwoCaptchaResult(
                        success=False,
                        error=result['error'],
                        task_id=task_id
                    )
                
                if result['status'] == 'ready':
                    solve_time = time.time() - start_time
                    logger.success(f"2captcha solved turnstile in {solve_time:.2f}s: {result['token'][:50]}...")
                    
                    return TwoCaptchaResult(
                        success=True,
                        token=result['token'],
                        user_agent=result.get('userAgent'),
                        task_id=task_id,
                        cost=result.get('cost'),
                        solve_time=solve_time
                    )
                elif result['status'] == 'processing':
                    elapsed = time.time() - poll_start
                    logger.info(f"2captcha still processing task {task_id} ({elapsed:.1f}s elapsed)")
                    continue
                else:
                    return TwoCaptchaResult(
                        success=False,
                        error=f"Unexpected status: {result['status']}",
                        task_id=task_id
                    )
            
            # Timeout reached
            return TwoCaptchaResult(
                success=False,
                error=f"Timeout after {self.timeout}s",
                task_id=task_id
            )
            
        except Exception as e:
            logger.error(f"2captcha solver error: {str(e)}")
            return TwoCaptchaResult(
                success=False,
                error=str(e)
            )
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance from 2captcha"""
        url = f"{self.BASE_URL}/getBalance"
        
        payload = {
            "clientKey": self.api_key
        }
        
        try:
            async with self.session.post(url, json=payload) as response:
                result = await response.json()
                
                if result.get('errorId', 0) != 0:
                    error_msg = result.get('errorDescription', f"Error ID: {result.get('errorId')}")
                    return {'success': False, 'error': error_msg}
                
                balance = result.get('balance')
                return {'success': True, 'balance': balance}
                
        except Exception as e:
            logger.error(f"Error getting 2captcha balance: {e}")
            return {'success': False, 'error': str(e)}


# Convenience function for backward compatibility
async def solve_turnstile_with_2captcha(
    api_key: str,
    website_url: str,
    website_key: str,
    action: Optional[str] = None,
    data: Optional[str] = None,
    pagedata: Optional[str] = None,
    proxy: Optional[str] = None,
    user_agent: Optional[str] = None,
    timeout: int = 120
) -> TwoCaptchaResult:
    """
    Convenience function to solve turnstile with 2captcha
    
    Args:
        api_key: Your 2captcha API key
        website_url: The full URL where the captcha is loaded
        website_key: Turnstile sitekey
        action: Action parameter for Cloudflare Challenge pages
        data: cData parameter for Cloudflare Challenge pages
        pagedata: chlPageData parameter for Cloudflare Challenge pages
        proxy: Proxy string (optional)
        user_agent: User agent string (optional)
        timeout: Maximum wait time in seconds
    
    Returns:
        TwoCaptchaResult with solution or error
    """
    async with TwoCaptchaTurnstileSolver(api_key, timeout) as solver:
        return await solver.solve_turnstile(
            website_url=website_url,
            website_key=website_key,
            action=action,
            data=data,
            pagedata=pagedata,
            proxy=proxy,
            user_agent=user_agent
        )


if __name__ == "__main__":
    # Example usage
    async def test_solver():
        api_key = "YOUR_2CAPTCHA_API_KEY"  # Replace with your actual API key
        
        # Test standalone captcha
        result = await solve_turnstile_with_2captcha(
            api_key=api_key,
            website_url="https://2captcha.com/demo/cloudflare-turnstile",
            website_key="3x00000000000000000000FF"
        )
        
        print(f"Result: {result}")
        
        # Test with proxy
        result_with_proxy = await solve_turnstile_with_2captcha(
            api_key=api_key,
            website_url="https://2captcha.com/demo/cloudflare-turnstile", 
            website_key="3x00000000000000000000FF",
            proxy="http://user:pass@proxy.example.com:8080"
        )
        
        print(f"Result with proxy: {result_with_proxy}")
    
    # Run test
    # asyncio.run(test_solver())
    print("2captcha Turnstile Solver loaded. Use solve_turnstile_with_2captcha() to solve captchas.")