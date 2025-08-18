#!/usr/bin/env python3
"""
Debug script to analyze Epic Games login page elements
Maps all form fields, buttons, and interactive elements for proper automation
"""

import asyncio
import logging
from patchright.async_api import async_playwright
from config.settings import LOGIN_URL
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_login_page():
    """Analyze the Epic Games login page to map all interactive elements"""
    
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
            if any(indicator in page_content.lower() for indicator in ['cloudflare', 'checking your browser', 'verifying']):
                logger.warning("🛡️ CloudFlare challenge detected - manual intervention may be needed")
                await asyncio.sleep(10)  # Wait for manual solving if needed
            
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
            
            # 5. Find any CAPTCHA/Turnstile elements
            captcha_selectors = [
                '[data-sitekey]',
                '.cf-turnstile',
                '.turnstile-wrapper',
                '.g-recaptcha',
                '.h-captcha',
                'iframe[src*="captcha"]',
                'iframe[src*="turnstile"]'
            ]
            
            logger.info("\n🛡️ CAPTCHA/TURNSTILE ELEMENTS:")
            captcha_elements = []
            for selector in captcha_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        sitekey = await element.get_attribute('data-sitekey')
                        element_id = await element.get_attribute('id')
                        element_class = await element.get_attribute('class')
                        is_visible = await element.is_visible()
                        
                        element_info = {
                            'selector': selector,
                            'sitekey': sitekey,
                            'id': element_id,
                            'class': element_class,
                            'visible': is_visible
                        }
                        captcha_elements.append(element_info)
                        logger.info(f"   ✅ {selector}: sitekey='{sitekey}', id='{element_id}', visible={is_visible}")
                except Exception as e:
                    logger.debug(f"   ⚠️ Error with selector {selector}: {e}")
            
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