#!/usr/bin/env python3
"""
Simple login page analysis using existing browser setup
"""

import asyncio
import logging
import json
from utils.browser_manager import BrowserManager
from config.settings import LOGIN_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_login_elements():
    """Analyze Epic Games login page elements"""
    
    browser_manager = BrowserManager()
    
    try:
        # Initialize browser manager
        await browser_manager.__aenter__()
        
        # Get browser and context with JavaScript and cookies enabled
        browser = await browser_manager.get_or_launch_browser(None)
        
        # Get a mobile user agent from the browser manager
        mobile_user_agent = browser_manager.get_next_user_agent()
        logger.info(f"🤖 Using mobile user agent: {mobile_user_agent}")
        
        context = await browser_manager.get_optimized_context(
            browser, 
            "__noproxy__",
            user_agent=mobile_user_agent
        )
        
        # Enable JavaScript and cookies explicitly
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        
        # Enable JavaScript (should be enabled by default, but let's be explicit)
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        logger.info("🌐 Navigating to Epic Games login page...")
        response = await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        
        if response:
            logger.info(f"📊 Response status: {response.status}")
        
        # Wait for page to load
        await asyncio.sleep(5)
        
        current_url = page.url
        logger.info(f"🔗 Current URL: {current_url}")
        
        # Take screenshot
        await page.screenshot(path="login_analysis.png", full_page=True)
        logger.info("📸 Screenshot saved")
        
        # Check for CloudFlare with enhanced detection
        page_content = await page.content()
        cf_indicators = [
            'cloudflare', 'checking your browser', 'verifying', 'turnstile',
            'something went wrong', 'enable javascript and cookies to continue',
            'window._cf_chl_opt', 'challenge-platform', 'cdn-cgi/challenge-platform',
            'cf_chl_opt', 'cray:', 'czone:', 'ctype:'
        ]
        
        has_cloudflare = any(indicator in page_content.lower() for indicator in cf_indicators)
        
        if has_cloudflare:
            logger.warning("🛡️ CloudFlare challenge detected on page")
            logger.info("⏳ Waiting for CloudFlare challenge to resolve...")
            
            # Wait up to 60 seconds for CloudFlare to resolve
            for i in range(60):
                await asyncio.sleep(1)
                current_content = await page.content()
                current_url = page.url
                
                # Check if challenge is resolved
                if not any(indicator in current_content.lower() for indicator in cf_indicators):
                    logger.info(f"✅ CloudFlare challenge resolved after {i+1} seconds")
                    break
                
                # Check if we've been redirected to login page
                if 'login' in current_url.lower() and '/error?' not in current_url.lower():
                    logger.info(f"✅ Redirected to login page after {i+1} seconds")
                    break
                
                if (i + 1) % 10 == 0:
                    logger.info(f"⏳ Still waiting for challenge resolution... ({i+1}s)")
            
            # Take another screenshot after potential resolution
            await page.screenshot(path="login_analysis_after_cf.png", full_page=True)
            logger.info("📸 Post-CloudFlare screenshot saved")
        else:
            logger.info("✅ No CloudFlare detected")
        
        # Analyze form elements
        logger.info("\n🔍 ANALYZING FORM ELEMENTS...")
        
        # Find forms
        forms = await page.query_selector_all('form')
        logger.info(f"📋 Found {len(forms)} form(s)")
        
        # Find input fields
        inputs = await page.query_selector_all('input')
        logger.info(f"📝 Found {len(inputs)} input field(s)")
        
        input_analysis = []
        for i, input_elem in enumerate(inputs):
            try:
                input_type = await input_elem.get_attribute('type') or 'text'
                input_name = await input_elem.get_attribute('name') or ''
                input_id = await input_elem.get_attribute('id') or ''
                input_placeholder = await input_elem.get_attribute('placeholder') or ''
                is_visible = await input_elem.is_visible()
                
                input_info = {
                    'index': i,
                    'type': input_type,
                    'name': input_name,
                    'id': input_id,
                    'placeholder': input_placeholder,
                    'visible': is_visible
                }
                input_analysis.append(input_info)
                
                if is_visible and input_type in ['email', 'text', 'password']:
                    logger.info(f"   Input {i}: type='{input_type}', name='{input_name}', id='{input_id}', placeholder='{input_placeholder}'")
            except Exception as e:
                logger.debug(f"Error analyzing input {i}: {e}")
        
        # Find buttons
        buttons = await page.query_selector_all('button')
        logger.info(f"🔘 Found {len(buttons)} button(s)")
        
        button_analysis = []
        for i, button in enumerate(buttons):
            try:
                button_type = await button.get_attribute('type') or ''
                button_text = await button.inner_text()
                button_id = await button.get_attribute('id') or ''
                button_class = await button.get_attribute('class') or ''
                is_visible = await button.is_visible()
                is_enabled = await button.is_enabled()
                
                button_info = {
                    'index': i,
                    'type': button_type,
                    'text': button_text.strip(),
                    'id': button_id,
                    'class': button_class,
                    'visible': is_visible,
                    'enabled': is_enabled
                }
                button_analysis.append(button_info)
                
                if is_visible and button_text.strip():
                    logger.info(f"   Button {i}: text='{button_text.strip()}', type='{button_type}', id='{button_id}', enabled={is_enabled}")
            except Exception as e:
                logger.debug(f"Error analyzing button {i}: {e}")
        
        # Look for specific Epic Games elements
        logger.info("\n🎮 LOOKING FOR EPIC GAMES SPECIFIC ELEMENTS...")
        
        # Common Epic Games selectors
        epic_selectors = [
            'input[name="email"]',
            'input[type="email"]',
            'input[name="password"]',
            'input[type="password"]',
            'button[type="submit"]',
            '[data-testid*="email"]',
            '[data-testid*="password"]',
            '[data-testid*="login"]',
            '[data-testid*="signin"]'
        ]
        
        found_elements = {}
        for selector in epic_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    found_elements[selector] = len(elements)
                    logger.info(f"   ✅ {selector}: {len(elements)} element(s)")
                    
                    # Get details of first element
                    first_elem = elements[0]
                    if await first_elem.is_visible():
                        elem_id = await first_elem.get_attribute('id')
                        elem_name = await first_elem.get_attribute('name')
                        elem_placeholder = await first_elem.get_attribute('placeholder')
                        logger.info(f"      First element: id='{elem_id}', name='{elem_name}', placeholder='{elem_placeholder}'")
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
        
        # Check for Turnstile elements
        logger.info("\n🛡️ CHECKING FOR TURNSTILE ELEMENTS...")
        turnstile_selectors = [
            '[data-sitekey]',
            '.cf-turnstile',
            '.turnstile-wrapper',
            'iframe[src*="turnstile"]'
        ]
        
        turnstile_found = []
        for selector in turnstile_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    sitekey = await elem.get_attribute('data-sitekey')
                    if sitekey:
                        turnstile_found.append({'selector': selector, 'sitekey': sitekey})
                        logger.info(f"   🎯 Turnstile found: {selector}, sitekey: {sitekey}")
            except Exception:
                continue
        
        # Save analysis results
        analysis_data = {
            'url': current_url,
            'has_cloudflare': has_cloudflare,
            'forms_count': len(forms),
            'inputs': input_analysis,
            'buttons': button_analysis,
            'epic_elements': found_elements,
            'turnstile_elements': turnstile_found
        }
        
        with open('login_elements_analysis.json', 'w') as f:
            json.dump(analysis_data, f, indent=2)
        
        logger.info("\n💾 Analysis saved to login_elements_analysis.json")
        
        # Test interaction with likely email field
        logger.info("\n🧪 TESTING EMAIL FIELD INTERACTION...")
        
        email_candidates = [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]'
        ]
        
        email_field_found = False
        for selector in email_candidates:
            try:
                email_field = await page.query_selector(selector)
                if email_field and await email_field.is_visible():
                    logger.info(f"   Testing email field: {selector}")
                    await email_field.click()
                    await email_field.fill("test@example.com")
                    value = await email_field.input_value()
                    logger.info(f"   ✅ Email field test successful: '{value}'")
                    await email_field.clear()
                    email_field_found = True
                    break
            except Exception as e:
                logger.debug(f"   ❌ Error testing {selector}: {e}")
        
        if not email_field_found:
            logger.warning("   ⚠️ No working email field found")
        
        # Test password field
        logger.info("\n🧪 TESTING PASSWORD FIELD INTERACTION...")
        
        password_candidates = [
            'input[type="password"]',
            'input[name="password"]'
        ]
        
        password_field_found = False
        for selector in password_candidates:
            try:
                password_field = await page.query_selector(selector)
                if password_field and await password_field.is_visible():
                    logger.info(f"   Testing password field: {selector}")
                    await password_field.click()
                    await password_field.fill("testpassword")
                    logger.info(f"   ✅ Password field test successful")
                    await password_field.clear()
                    password_field_found = True
                    break
            except Exception as e:
                logger.debug(f"   ❌ Error testing {selector}: {e}")
        
        if not password_field_found:
            logger.warning("   ⚠️ No working password field found")
        
        logger.info("\n✅ Analysis complete!")
        
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        try:
            await page.screenshot(path="analysis_error.png")
        except:
            pass
    
    finally:
        try:
            await browser_manager.__aexit__(None, None, None)
        except:
            pass

if __name__ == "__main__":
    asyncio.run(analyze_login_elements())