"""
Cloudflare Challenge Parameter Extractor
Extracts cData, chlPageData, and action parameters from Cloudflare Challenge pages
Based on 2captcha documentation for handling complex Cloudflare Challenge pages
"""

import asyncio
import logging
from typing import Dict, Any, Optional
try:
    from patchright.async_api import Page
except ImportError:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

class CloudflareParameterExtractor:
    """
    Extracts parameters required for solving Turnstile on Cloudflare Challenge pages
    
    Based on 2captcha documentation:
    https://2captcha.com/api-docs/cloudflare-turnstile#cloudflare-challenge-page
    """
    
    # JavaScript injection to intercept turnstile.render parameters
    TURNSTILE_INTERCEPT_JS = """
    (function() {
        console.log('🔍 Cloudflare Challenge Parameter Extractor - Injecting turnstile interceptor...');
        
        // Store original parameters
        window.cfChallengeParams = {
            extracted: false,
            sitekey: null,
            action: null,
            cData: null,
            chlPageData: null,
            callback: null,
            userAgent: navigator.userAgent,
            url: window.location.href
        };
        
        // Set up interval to intercept turnstile when it loads
        const interceptInterval = setInterval(() => {
            if (window.turnstile && !window.cfChallengeParams.extracted) {
                console.log('🎯 Found turnstile object, intercepting render method...');
                clearInterval(interceptInterval);
                
                // Store original render method
                const originalRender = window.turnstile.render;
                
                // Override render method to capture parameters
                window.turnstile.render = function(container, options) {
                    console.log('🔥 Turnstile render intercepted!', options);
                    
                    // Extract parameters
                    window.cfChallengeParams = {
                        extracted: true,
                        sitekey: options.sitekey || options['site-key'],
                        action: options.action,
                        cData: options.cData,
                        chlPageData: options.chlPageData,
                        callback: options.callback,
                        userAgent: navigator.userAgent,
                        url: window.location.href,
                        container: container,
                        options: options
                    };
                    
                    console.log('✅ Extracted Cloudflare Challenge parameters:', window.cfChallengeParams);
                    
                    // Store callback globally for later use
                    if (options.callback) {
                        window.cfTurnstileCallback = options.callback;
                    }
                    
                    // Return a dummy element ID to prevent errors
                    return 'cf-challenge-intercepted';
                };
                
                console.log('✅ Turnstile render method intercepted successfully');
            }
        }, 100);
        
        // Cleanup after 30 seconds if turnstile not found
        setTimeout(() => {
            clearInterval(interceptInterval);
            if (!window.cfChallengeParams.extracted) {
                console.log('⚠️ Turnstile not found within 30 seconds');
            }
        }, 30000);
        
        console.log('🚀 Cloudflare Challenge Parameter Extractor initialized');
    })();
    """
    
    # Alternative method: intercept api.js script loading
    API_JS_INTERCEPT_JS = """
    (function() {
        console.log('🔍 Intercepting Cloudflare api.js script loading...');
        
        // Override fetch to intercept api.js requests
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const url = args[0];
            if (typeof url === 'string' && url.includes('challenges.cloudflare.com/turnstile/v0/api.js')) {
                console.log('🎯 Intercepted api.js request:', url);
                
                // Return a custom response that exposes parameters
                return Promise.resolve(new Response(`
                    console.log('🔥 Custom api.js loaded');
                    window.turnstile = {
                        render: function(container, options) {
                            console.log('🎯 Custom turnstile.render called with:', options);
                            
                            window.cfChallengeParams = {
                                extracted: true,
                                sitekey: options.sitekey || options['site-key'],
                                action: options.action,
                                cData: options.cData,
                                chlPageData: options.chlPageData,
                                callback: options.callback,
                                userAgent: navigator.userAgent,
                                url: window.location.href,
                                container: container,
                                options: options
                            };
                            
                            if (options.callback) {
                                window.cfTurnstileCallback = options.callback;
                            }
                            
                            console.log('✅ Parameters extracted via api.js intercept:', window.cfChallengeParams);
                            return 'cf-api-intercepted';
                        }
                    };
                `, {
                    status: 200,
                    statusText: 'OK',
                    headers: { 'Content-Type': 'application/javascript' }
                }));
            }
            
            return originalFetch.apply(this, args);
        };
        
        console.log('✅ api.js intercept initialized');
    })();
    """
    
    @staticmethod
    async def inject_parameter_extractor(page: Page, method: str = "render") -> bool:
        """
        Inject JavaScript to extract Cloudflare Challenge parameters
        
        Args:
            page: Playwright page object
            method: Extraction method ("render" or "api_js")
        
        Returns:
            bool: True if injection successful
        """
        try:
            if method == "render":
                await page.evaluate(CloudflareParameterExtractor.TURNSTILE_INTERCEPT_JS)
                logger.info("🔥 Injected turnstile.render interceptor")
            elif method == "api_js":
                await page.evaluate(CloudflareParameterExtractor.API_JS_INTERCEPT_JS)
                logger.info("🔥 Injected api.js interceptor")
            else:
                logger.error(f"Unknown extraction method: {method}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to inject parameter extractor: {e}")
            return False
    
    @staticmethod
    async def extract_challenge_parameters(
        page: Page, 
        timeout: int = 30,
        method: str = "render"
    ) -> Dict[str, Any]:
        """
        Extract Cloudflare Challenge parameters from the page
        
        Args:
            page: Playwright page object
            timeout: Maximum time to wait for parameters (seconds)
            method: Extraction method ("render" or "api_js")
        
        Returns:
            Dict containing extracted parameters or error info
        """
        try:
            # Inject the parameter extractor
            injection_success = await CloudflareParameterExtractor.inject_parameter_extractor(page, method)
            if not injection_success:
                return {
                    'success': False,
                    'error': 'Failed to inject parameter extractor'
                }
            
            logger.info(f"🔍 Waiting up to {timeout}s for Cloudflare Challenge parameters...")
            
            # Wait for parameters to be extracted
            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    # Check if parameters have been extracted
                    params = await page.evaluate("""
                        () => {
                            if (window.cfChallengeParams && window.cfChallengeParams.extracted) {
                                return window.cfChallengeParams;
                            }
                            return null;
                        }
                    """)
                    
                    if params:
                        logger.success(f"✅ Extracted Cloudflare Challenge parameters: sitekey={params.get('sitekey')}")
                        return {
                            'success': True,
                            'sitekey': params.get('sitekey'),
                            'action': params.get('action'),
                            'cData': params.get('cData'),
                            'chlPageData': params.get('chlPageData'),
                            'callback': params.get('callback'),
                            'userAgent': params.get('userAgent'),
                            'url': params.get('url'),
                            'method': method,
                            'raw_params': params
                        }
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.debug(f"Error checking parameters: {e}")
                    await asyncio.sleep(1)
            
            # Timeout reached
            logger.warning(f"⚠️ Timeout waiting for Cloudflare Challenge parameters ({timeout}s)")
            
            # Try to get any partial data
            try:
                partial_params = await page.evaluate("""
                    () => {
                        return {
                            cfChallengeParams: window.cfChallengeParams || null,
                            turnstileExists: !!window.turnstile,
                            url: window.location.href,
                            userAgent: navigator.userAgent
                        };
                    }
                """)
                
                return {
                    'success': False,
                    'error': f'Timeout after {timeout}s',
                    'partial_data': partial_params,
                    'method': method
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Timeout after {timeout}s, failed to get partial data: {str(e)}',
                    'method': method
                }
            
        except Exception as e:
            logger.error(f"Error extracting Cloudflare Challenge parameters: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': method
            }
    
    @staticmethod
    async def execute_callback_with_token(page: Page, token: str) -> bool:
        """
        Execute the Cloudflare Challenge callback with the solved token
        
        Args:
            page: Playwright page object
            token: Solved turnstile token from 2captcha
        
        Returns:
            bool: True if callback executed successfully
        """
        try:
            # Execute the callback with the token
            result = await page.evaluate(f"""
                (token) => {{
                    console.log('🔥 Executing Cloudflare Challenge callback with token:', token);
                    
                    if (window.cfTurnstileCallback && typeof window.cfTurnstileCallback === 'function') {{
                        try {{
                            window.cfTurnstileCallback(token);
                            console.log('✅ Callback executed successfully');
                            return {{ success: true, method: 'callback' }};
                        }} catch (e) {{
                            console.error('❌ Callback execution failed:', e);
                            return {{ success: false, error: e.toString(), method: 'callback' }};
                        }}
                    }}
                    
                    // Fallback: try to set the token in common input fields
                    const inputs = [
                        'input[name="cf-turnstile-response"]',
                        'input[name="g-recaptcha-response"]',
                        'textarea[name="cf-turnstile-response"]',
                        'textarea[name="g-recaptcha-response"]'
                    ];
                    
                    let inputSet = false;
                    for (const selector of inputs) {{
                        const input = document.querySelector(selector);
                        if (input) {{
                            input.value = token;
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            inputSet = true;
                            console.log('✅ Token set in input field:', selector);
                        }}
                    }}
                    
                    if (inputSet) {{
                        return {{ success: true, method: 'input_field' }};
                    }}
                    
                    console.log('⚠️ No callback or input field found');
                    return {{ success: false, error: 'No callback or input field found', method: 'none' }};
                }}
            """, token)
            
            if result.get('success'):
                logger.success(f"✅ Token applied successfully via {result.get('method')}")
                return True
            else:
                logger.error(f"❌ Failed to apply token: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing callback with token: {e}")
            return False


# Convenience function
async def extract_cloudflare_challenge_params(
    page: Page,
    timeout: int = 30,
    method: str = "render"
) -> Dict[str, Any]:
    """
    Convenience function to extract Cloudflare Challenge parameters
    
    Args:
        page: Playwright page object
        timeout: Maximum time to wait for parameters (seconds)
        method: Extraction method ("render" or "api_js")
    
    Returns:
        Dict containing extracted parameters or error info
    """
    return await CloudflareParameterExtractor.extract_challenge_parameters(page, timeout, method)


if __name__ == "__main__":
    print("Cloudflare Challenge Parameter Extractor loaded.")
    print("Use extract_cloudflare_challenge_params() to extract parameters from challenge pages.")