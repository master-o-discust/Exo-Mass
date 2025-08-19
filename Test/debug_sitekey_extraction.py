#!/usr/bin/env python3
"""
Debug Sitekey Extraction
This script debugs the sitekey extraction to see what's happening
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from utils.browser_manager import BrowserManager
from utils.file_manager import FileManager
from utils.enhanced_sitekey_extractor import EnhancedSitekeyExtractor
from config.settings import LOGIN_URL

class SitekeyDebugger:
    """Debug sitekey extraction"""
    
    def __init__(self):
        self.proxies = []
        
    async def debug_sitekey_extraction(self):
        """Debug the sitekey extraction process"""
        logger.info("🔍 DEBUGGING SITEKEY EXTRACTION")
        logger.info("=" * 60)
        
        # Load test data
        await self.load_test_data()
        
        # Initialize browser manager
        browser_manager = BrowserManager(self.proxies)
        
        try:
            async with browser_manager:
                # Setup browser
                proxy = browser_manager.get_proxy_for_check() if self.proxies else None
                user_agent = browser_manager.get_next_user_agent()
                browser = await browser_manager.get_or_launch_browser(proxy)
                proxy_key = f"{proxy or '__noproxy__'}"
                context = await browser_manager.get_optimized_context(browser, proxy_key, user_agent=user_agent)
                
                # Create page
                page = await context.new_page()
                
                try:
                    # Step 1: Navigate to login page
                    logger.info("🌐 Step 1: Navigating to login page...")
                    await page.goto(LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(5)
                    
                    # Fill login form to trigger challenge
                    logger.info("📝 Step 2: Filling login form to trigger challenge...")
                    
                    # Fill email
                    await page.evaluate("""
                        () => {
                            const emailField = document.querySelector('input[type="email"], input[name="email"], #email');
                            if (emailField) {
                                emailField.value = 'test@example.com';
                                emailField.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        }
                    """)
                    
                    # Click continue
                    continue_btn = await page.query_selector('button:has-text("Continue")')
                    if continue_btn:
                        await continue_btn.click()
                        await asyncio.sleep(3)
                    
                    # Fill password
                    await page.evaluate("""
                        () => {
                            const passwordField = document.querySelector('input[type="password"], input[name="password"], #password');
                            if (passwordField) {
                                passwordField.value = 'testpassword123';
                                passwordField.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        }
                    """)
                    
                    # Click sign in to trigger challenge
                    signin_btn = await page.query_selector('button:has-text("Sign in")')
                    if signin_btn:
                        await signin_btn.click()
                        await asyncio.sleep(5)  # Wait for challenge to appear
                    else:
                        await page.keyboard.press('Enter')
                        await asyncio.sleep(5)
                    
                    # Step 3: Debug current page state
                    logger.info("🔍 Step 3: Debugging current page state...")
                    current_url = page.url
                    logger.info(f"📍 Current URL: {current_url}")
                    
                    # Get page title
                    title = await page.title()
                    logger.info(f"📄 Page title: {title}")
                    
                    # Check for challenge elements
                    logger.info("🔍 Looking for challenge elements...")
                    
                    # Check for Cloudflare elements
                    cf_elements = await page.query_selector_all('[class*="challenge"], [id*="challenge"], [data-sitekey], .cf-turnstile, #cf-turnstile')
                    logger.info(f"🎯 Found {len(cf_elements)} potential challenge elements")
                    
                    for i, element in enumerate(cf_elements):
                        try:
                            tag_name = await element.evaluate('el => el.tagName')
                            class_name = await element.get_attribute('class') or 'None'
                            id_attr = await element.get_attribute('id') or 'None'
                            data_sitekey = await element.get_attribute('data-sitekey') or 'None'
                            is_visible = await element.is_visible()
                            
                            logger.info(f"  Element {i+1}: {tag_name} class='{class_name}' id='{id_attr}' data-sitekey='{data_sitekey}' visible={is_visible}")
                        except Exception as e:
                            logger.warning(f"  Element {i+1}: Error getting info - {e}")
                    
                    # Check page source for sitekey patterns
                    logger.info("🔍 Checking page source for sitekey patterns...")
                    page_content = await page.content()
                    
                    import re
                    sitekey_patterns = [
                        r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'data-sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'"sitekey"\s*:\s*"([^"]+)"',
                        r'0x[A-Za-z0-9_-]{20,}',  # Generic sitekey pattern
                    ]
                    
                    for pattern in sitekey_patterns:
                        matches = re.findall(pattern, page_content, re.IGNORECASE)
                        if matches:
                            logger.info(f"✅ Pattern '{pattern}' found matches: {matches}")
                        else:
                            logger.debug(f"❌ Pattern '{pattern}' found no matches")
                    
                    # Check JavaScript objects
                    logger.info("🔍 Checking JavaScript objects...")
                    js_result = await page.evaluate("""
                        () => {
                            const result = {};
                            
                            // Check window object
                            if (window.cf) result.cf = window.cf;
                            if (window.turnstile) result.turnstile = window.turnstile;
                            if (window.cloudflare) result.cloudflare = window.cloudflare;
                            
                            // Check for any sitekey variables
                            const scripts = document.querySelectorAll('script');
                            const scriptContents = [];
                            for (let script of scripts) {
                                const content = script.textContent || script.innerHTML;
                                if (content.includes('sitekey') || content.includes('0x')) {
                                    scriptContents.push(content.substring(0, 200) + '...');
                                }
                            }
                            result.scriptContents = scriptContents;
                            
                            return result;
                        }
                    """)
                    
                    logger.info(f"🔍 JavaScript objects: {js_result}")
                    
                    # Take a debug screenshot
                    await page.screenshot(path="debug_sitekey_extraction.png", full_page=True)
                    logger.info("📸 Debug screenshot saved")
                    
                    # Step 4: Try enhanced extraction
                    logger.info("🔍 Step 4: Testing enhanced sitekey extraction...")
                    extracted_sitekey = await EnhancedSitekeyExtractor.extract_sitekey_comprehensive(page)
                    
                    if extracted_sitekey:
                        logger.info(f"✅ Enhanced extraction SUCCESS: {extracted_sitekey}")
                        return True
                    else:
                        logger.warning("❌ Enhanced extraction FAILED - no sitekey found")
                        return False
                    
                finally:
                    await page.close()
                    
        except Exception as e:
            logger.error(f"❌ Debug failed: {e}")
            return False
    
    async def load_test_data(self):
        """Load test data"""
        # Load proxies
        proxy_file = project_root / "Proxy.txt"
        if proxy_file.exists():
            self.proxies = await FileManager.read_proxies(str(proxy_file))
            logger.info(f"✅ Loaded {len(self.proxies)} proxies")

async def main():
    """Main debug execution"""
    debugger = SitekeyDebugger()
    
    try:
        success = await debugger.debug_sitekey_extraction()
        
        logger.info("\n" + "=" * 60)
        if success:
            logger.info("🎉 SITEKEY EXTRACTION DEBUG COMPLETED SUCCESSFULLY!")
            return 0
        else:
            logger.warning("⚠️ SITEKEY EXTRACTION DEBUG FOUND ISSUES")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Debug interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Debug failed: {e}")
        return 1

if __name__ == "__main__":
    os.chdir(project_root)
    exit_code = asyncio.run(main())
    sys.exit(exit_code)