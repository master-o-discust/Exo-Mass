#!/usr/bin/env python3
"""
Debug script to analyze Epic Games login page elements
Maps all form fields, buttons, and interactive elements for proper automation
"""

import asyncio
import logging
from playwright.async_api import async_playwright
from config.settings import LOGIN_URL
from utils.unified_turnstile_handler import create_turnstile_handler
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def detect_turnstile_elements(page, extended=False):
    """
    Enhanced Turnstile/CAPTCHA detection with comprehensive sitekey extraction
    Based on best practices from 2captcha and other professional tools
    """
    captcha_elements = []
    
    # Primary Turnstile selectors (most common patterns)
    primary_selectors = [
        # Cloudflare Turnstile
        'div[data-sitekey]',  # Most common
        '#cf-turnstile',      # Standard ID
        '.cf-turnstile',      # Standard class
        'div.cf-turnstile',   # Specific div with class
        '[data-sitekey*="0x"]',  # Turnstile sitekeys start with 0x
        
        # Generic CAPTCHA containers
        '.turnstile-wrapper',
        '.turnstile-container',
        '[class*="turnstile"]',
        '[id*="turnstile"]',
        
        # reCAPTCHA (for comparison)
        '.g-recaptcha',
        'div[data-sitekey*="6L"]',  # reCAPTCHA sitekeys start with 6L
        
        # hCaptcha
        '.h-captcha',
        'div[data-sitekey*="h"]',   # Some hCaptcha patterns
    ]
    
    # Extended selectors for deeper search
    extended_selectors = [
        # Shadow DOM and iframe patterns
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="turnstile"]',
        'iframe[src*="captcha"]',
        
        # Generic data attributes
        '[data-cf-turnstile-sitekey]',
        '[data-turnstile-sitekey]',
        '[data-captcha-sitekey]',
        
        # Form-related patterns
        'form [data-sitekey]',
        'div[role="presentation"][data-sitekey]',
        
        # Dynamic content patterns
        '[class*="challenge"]',
        '[id*="challenge"]',
        '[class*="captcha"]',
        '[id*="captcha"]',
    ]
    
    selectors_to_check = primary_selectors
    if extended:
        selectors_to_check.extend(extended_selectors)
    
    for selector in selectors_to_check:
        try:
            elements = await page.query_selector_all(selector)
            for element in elements:
                # Extract comprehensive element information
                element_info = await extract_element_info(element, selector)
                if element_info and element_info not in captcha_elements:
                    captcha_elements.append(element_info)
                    
        except Exception as e:
            logger.debug(f"Error with selector {selector}: {e}")
    
    # Additional check: scan for hidden inputs with turnstile response
    try:
        response_inputs = await page.query_selector_all('input[name*="turnstile"], input[name*="cf-turnstile-response"]')
        for input_elem in response_inputs:
            parent = await input_elem.query_selector('xpath=..')
            if parent:
                parent_info = await extract_element_info(parent, 'input[name*="turnstile"] parent')
                if parent_info and parent_info not in captcha_elements:
                    captcha_elements.append(parent_info)
    except Exception as e:
        logger.debug(f"Error checking turnstile response inputs: {e}")
    
    return captcha_elements

async def extract_element_info(element, selector):
    """Extract comprehensive information from a potential CAPTCHA element"""
    try:
        # Basic attributes
        sitekey = await element.get_attribute('data-sitekey')
        element_id = await element.get_attribute('id')
        element_class = await element.get_attribute('class')
        is_visible = await element.is_visible()
        
        # Additional sitekey extraction methods
        if not sitekey:
            # Try alternative sitekey attributes
            alt_sitekey_attrs = [
                'data-cf-turnstile-sitekey',
                'data-turnstile-sitekey',
                'data-captcha-sitekey',
                'data-site-key',
                'sitekey'
            ]
            for attr in alt_sitekey_attrs:
                sitekey = await element.get_attribute(attr)
                if sitekey:
                    break
        
        # Determine CAPTCHA type
        captcha_type = "Unknown"
        if sitekey:
            if sitekey.startswith('0x'):
                captcha_type = "Cloudflare Turnstile"
            elif sitekey.startswith('6L'):
                captcha_type = "reCAPTCHA"
            elif 'h-captcha' in (element_class or '').lower():
                captcha_type = "hCaptcha"
            else:
                captcha_type = "Generic CAPTCHA"
        
        # Additional attributes for debugging
        additional_attrs = {}
        for attr in ['data-theme', 'data-size', 'data-callback', 'data-action', 'data-appearance']:
            value = await element.get_attribute(attr)
            if value:
                additional_attrs[attr] = value
        
        # Get element dimensions and position
        try:
            bounding_box = await element.bounding_box()
            if bounding_box:
                additional_attrs['dimensions'] = f"{bounding_box['width']}x{bounding_box['height']}"
                additional_attrs['position'] = f"({bounding_box['x']}, {bounding_box['y']})"
        except:
            pass
        
        return {
            'type': captcha_type,
            'selector': selector,
            'sitekey': sitekey,
            'id': element_id,
            'class': element_class,
            'visible': is_visible,
            'additional_attrs': additional_attrs if additional_attrs else None
        }
        
    except Exception as e:
        logger.debug(f"Error extracting element info: {e}")
        return None

async def analyze_login_page():
    """Analyze the Epic Games login page to map all interactive elements"""
    
    # Create turnstile handler for CloudFlare challenge solving
    turnstile_handler = create_turnstile_handler()
    
    async with async_playwright() as p:
        # Launch browser with realistic settings
        browser = await p.firefox.launch(
            headless=True,  # Run headless for server environment
            args=[
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
        )
        
        page = await context.new_page()
        
        try:
            logger.info("🌐 Navigating to Epic Games login page...")
            response = await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
            
            if response:
                logger.info(f"📊 Response status: {response.status}")
            
            # Wait for page to fully load
            await asyncio.sleep(5)
            
            current_url = page.url
            logger.info(f"🔗 Current URL: {current_url}")
            
            # Check if we're blocked by CloudFlare
            page_content = await page.content()
            cloudflare_indicators = [
                'cloudflare', 'checking your browser', 'verifying', 'turnstile',
                'enable javascript and cookies to continue', 'challenge-platform',
                'cdn-cgi/challenge-platform', '_cf_chl_opt', 'window._cf_chl_opt'
            ]
            
            if any(indicator in page_content.lower() for indicator in cloudflare_indicators):
                logger.warning("🛡️ CloudFlare challenge detected - attempting to solve with Turnstile handler...")
                
                # Use the unified turnstile handler to solve the challenge
                challenge_result = await turnstile_handler.solve_turnstile_challenge(page)
                
                if challenge_result.get('success'):
                    logger.info("✅ CloudFlare challenge solved successfully!")
                    # Wait for page to settle after challenge resolution
                    await asyncio.sleep(5)
                    
                    # Check if we're now on the correct page
                    current_url = page.url
                    logger.info(f"🔗 URL after challenge resolution: {current_url}")
                    
                    # Take another screenshot after resolution
                    await page.screenshot(path="login_page_after_cf.png", full_page=True)
                    logger.info("📸 Post-CloudFlare screenshot saved")
                else:
                    logger.error(f"❌ Failed to solve CloudFlare challenge: {challenge_result.get('error', 'Unknown error')}")
                    # Still take a screenshot for debugging
                    await page.screenshot(path="login_page_cf_failed.png", full_page=True)
                    logger.info("📸 CloudFlare failure screenshot saved")
            else:
                logger.info("✅ No CloudFlare challenge detected")
            
            # Take screenshot
            await page.screenshot(path="login_page_analysis.png", full_page=True)
            logger.info("📸 Screenshot saved as login_page_analysis.png")
            
            # Analyze page structure
            logger.info("\n🔍 ANALYZING PAGE STRUCTURE...")
            
            # 1. Find all form elements
            forms = await page.query_selector_all('form')
            logger.info(f"📋 Found {len(forms)} form(s)")
            
            for i, form in enumerate(forms):
                form_id = await form.get_attribute('id')
                form_class = await form.get_attribute('class')
                form_action = await form.get_attribute('action')
                logger.info(f"   Form {i+1}: id='{form_id}', class='{form_class}', action='{form_action}'")
            
            # 2. Find email/username input fields
            email_selectors = [
                'input[type="email"]',
                'input[name*="email"]',
                'input[id*="email"]',
                'input[placeholder*="email"]',
                'input[name*="username"]',
                'input[id*="username"]',
                'input[placeholder*="username"]',
                'input[name*="user"]',
                'input[id*="user"]'
            ]
            
            logger.info("\n📧 EMAIL/USERNAME FIELDS:")
            email_elements = []
            for selector in email_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    element_id = await element.get_attribute('id')
                    element_name = await element.get_attribute('name')
                    element_placeholder = await element.get_attribute('placeholder')
                    element_type = await element.get_attribute('type')
                    is_visible = await element.is_visible()
                    
                    element_info = {
                        'selector': selector,
                        'id': element_id,
                        'name': element_name,
                        'placeholder': element_placeholder,
                        'type': element_type,
                        'visible': is_visible
                    }
                    email_elements.append(element_info)
                    logger.info(f"   ✅ {selector}: id='{element_id}', name='{element_name}', placeholder='{element_placeholder}', visible={is_visible}")
            
            # 3. Find password input fields
            password_selectors = [
                'input[type="password"]',
                'input[name*="password"]',
                'input[id*="password"]',
                'input[placeholder*="password"]',
                'input[name*="pass"]',
                'input[id*="pass"]'
            ]
            
            logger.info("\n🔒 PASSWORD FIELDS:")
            password_elements = []
            for selector in password_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    element_id = await element.get_attribute('id')
                    element_name = await element.get_attribute('name')
                    element_placeholder = await element.get_attribute('placeholder')
                    is_visible = await element.is_visible()
                    
                    element_info = {
                        'selector': selector,
                        'id': element_id,
                        'name': element_name,
                        'placeholder': element_placeholder,
                        'visible': is_visible
                    }
                    password_elements.append(element_info)
                    logger.info(f"   ✅ {selector}: id='{element_id}', name='{element_name}', placeholder='{element_placeholder}', visible={is_visible}")
            
            # 4. Find submit buttons
            button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign In")',
                'button:has-text("Login")',
                'button:has-text("Log In")',
                'button:has-text("Continue")',
                'button[id*="login"]',
                'button[id*="signin"]',
                'button[class*="login"]',
                'button[class*="signin"]',
                'a[href*="login"]'
            ]
            
            logger.info("\n🔘 SUBMIT BUTTONS:")
            button_elements = []
            for selector in button_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        element_id = await element.get_attribute('id')
                        element_class = await element.get_attribute('class')
                        element_text = await element.inner_text()
                        element_type = await element.get_attribute('type')
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        
                        element_info = {
                            'selector': selector,
                            'id': element_id,
                            'class': element_class,
                            'text': element_text,
                            'type': element_type,
                            'visible': is_visible,
                            'enabled': is_enabled
                        }
                        button_elements.append(element_info)
                        logger.info(f"   ✅ {selector}: id='{element_id}', text='{element_text}', visible={is_visible}, enabled={is_enabled}")
                except Exception as e:
                    logger.debug(f"   ⚠️ Error with selector {selector}: {e}")
            
            # 5. Enhanced CAPTCHA/Turnstile detection with improved sitekey extraction
            logger.info("\n🛡️ CAPTCHA/TURNSTILE ELEMENTS (Enhanced Detection):")
            captcha_elements = await detect_turnstile_elements(page)
            
            for element_info in captcha_elements:
                logger.info(f"   ✅ {element_info['type']}: {element_info['selector']}")
                logger.info(f"      🔑 Sitekey: '{element_info['sitekey']}'")
                logger.info(f"      🆔 ID: '{element_info['id']}'")
                logger.info(f"      👁️ Visible: {element_info['visible']}")
                if element_info.get('additional_attrs'):
                    logger.info(f"      📋 Additional: {element_info['additional_attrs']}")
            
            if not captcha_elements:
                logger.info("   ⚠️ No CAPTCHA/Turnstile elements detected initially")
                logger.info("   🔄 Waiting for dynamic content to load...")
                
                # Wait for potential dynamic content
                await asyncio.sleep(5)
                
                # Try again with extended detection
                captcha_elements = await detect_turnstile_elements(page, extended=True)
                
                if captcha_elements:
                    logger.info("   ✅ Found CAPTCHA elements after waiting:")
                    for element_info in captcha_elements:
                        logger.info(f"      🔑 {element_info['type']}: sitekey='{element_info['sitekey']}'")
                else:
                    logger.info("   ❌ No CAPTCHA/Turnstile elements found even after waiting")
            
            # 6. Check for any error messages or notifications
            error_selectors = [
                '.error',
                '.alert',
                '.notification',
                '[class*="error"]',
                '[class*="alert"]',
                '[id*="error"]',
                '[role="alert"]'
            ]
            
            logger.info("\n⚠️ ERROR/ALERT ELEMENTS:")
            for selector in error_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        if await element.is_visible():
                            text = await element.inner_text()
                            if text.strip():
                                logger.info(f"   ⚠️ {selector}: '{text.strip()}'")
                except Exception:
                    continue
            
            # 7. Save analysis results to JSON
            analysis_results = {
                'url': current_url,
                'timestamp': str(asyncio.get_event_loop().time()),
                'email_elements': email_elements,
                'password_elements': password_elements,
                'button_elements': button_elements,
                'captcha_elements': captcha_elements
            }
            
            with open('login_page_analysis.json', 'w') as f:
                json.dump(analysis_results, f, indent=2)
            
            logger.info("\n💾 Analysis results saved to login_page_analysis.json")
            
            # 8. Test form interaction
            logger.info("\n🧪 TESTING FORM INTERACTION...")
            
            # Find the best email field
            best_email_field = None
            for element_info in email_elements:
                if element_info['visible'] and element_info['type'] == 'email':
                    best_email_field = element_info
                    break
            
            if not best_email_field:
                for element_info in email_elements:
                    if element_info['visible']:
                        best_email_field = element_info
                        break
            
            if best_email_field:
                logger.info(f"🎯 Best email field: {best_email_field['selector']}")
                
                # Test filling the email field
                try:
                    if best_email_field['id']:
                        email_element = await page.query_selector(f"#{best_email_field['id']}")
                    elif best_email_field['name']:
                        email_element = await page.query_selector(f"[name='{best_email_field['name']}']")
                    else:
                        email_element = await page.query_selector(best_email_field['selector'])
                    
                    if email_element:
                        await email_element.click()
                        await email_element.fill("test@example.com")
                        logger.info("✅ Successfully filled email field")
                        
                        # Clear it
                        await email_element.clear()
                        logger.info("✅ Successfully cleared email field")
                except Exception as e:
                    logger.error(f"❌ Error testing email field: {e}")
            
            # Wait for manual inspection
            logger.info("\n⏳ Waiting 30 seconds for manual inspection...")
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"❌ Error during analysis: {e}")
            await page.screenshot(path="error_screenshot.png")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_login_page())