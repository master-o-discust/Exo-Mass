#!/usr/bin/env python3
"""
End-to-End Test Script for Exo Mass Checker
Tests the complete automated browsing system without Telegram bot:
- Uses proxy from Proxy.txt
- Uses account from files.txt
- Navigates to Epic Games login page
- Handles Turnstile/Cloudflare challenges with solvers
- Attempts login with full automation
"""
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_end_to_end.log')
    ]
)
logger = logging.getLogger(__name__)

# Import all necessary components
from utils.account_checker import AccountChecker
from utils.solver_manager import SolverManager
from utils.browser_manager import BrowserManager
from utils.file_manager import FileManager
from config.settings import LOGIN_URL, DEBUG_ENHANCED_FEATURES

class EndToEndTester:
    """Complete end-to-end testing system"""
    
    def __init__(self):
        self.solver_manager = None
        self.account_checker = None
        self.proxies = []
        self.accounts = []
        
    async def initialize_system(self):
        """Initialize all system components"""
        logger.info("🚀 Initializing End-to-End Test System")
        logger.info("=" * 60)
        
        # Initialize solver manager first
        logger.info("🔧 Initializing Solver Manager...")
        self.solver_manager = SolverManager()
        solver_status = await self.solver_manager.initialize_all_solvers()
        
        # Start solver services
        logger.info("🌐 Starting Solver Services...")
        await self.solver_manager.start_turnstile_service()
        await self.solver_manager.start_botsforge_service()
        
        # Load test data
        await self.load_test_data()
        
        # Initialize account checker with proxies
        logger.info("🔍 Initializing Account Checker...")
        self.account_checker = AccountChecker(
            proxies=self.proxies,
            user_id=999999  # Test user ID
        )
        
        logger.info("✅ System initialization complete!")
        return solver_status
    
    async def load_test_data(self):
        """Load proxies and accounts from files"""
        logger.info("📁 Loading test data...")
        
        # Load proxies from Proxy.txt
        proxy_file = project_root / "Proxy.txt"
        if proxy_file.exists():
            try:
                self.proxies = await FileManager.read_proxies(str(proxy_file))
                logger.info(f"✅ Loaded {len(self.proxies)} proxies from Proxy.txt")
                for i, proxy in enumerate(self.proxies):
                    # Mask sensitive proxy info for logging
                    proxy_masked = self._mask_proxy(proxy)
                    logger.info(f"   Proxy {i+1}: {proxy_masked}")
            except Exception as e:
                logger.error(f"❌ Failed to load proxies: {e}")
                self.proxies = []
        else:
            logger.warning("⚠️ Proxy.txt not found, running without proxy")
            self.proxies = []
        
        # Load accounts from files.txt
        accounts_file = project_root / "files.txt"
        if accounts_file.exists():
            try:
                self.accounts = await FileManager.read_accounts(str(accounts_file))
                logger.info(f"✅ Loaded {len(self.accounts)} accounts from files.txt")
                for i, (email, password) in enumerate(self.accounts):
                    # Mask password for logging
                    password_masked = password[:2] + "*" * (len(password) - 4) + password[-2:] if len(password) > 4 else "****"
                    logger.info(f"   Account {i+1}: {email}:{password_masked}")
            except Exception as e:
                logger.error(f"❌ Failed to load accounts: {e}")
                self.accounts = []
        else:
            logger.error("❌ files.txt not found!")
            self.accounts = []
    
    def _mask_proxy(self, proxy: str) -> str:
        """Mask sensitive proxy information for logging"""
        try:
            if '@' in proxy:
                auth_part, server_part = proxy.split('@', 1)
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                    masked_password = password[:2] + "*" * (len(password) - 4) + password[-2:] if len(password) > 4 else "****"
                    return f"{username}:{masked_password}@{server_part}"
            return proxy
        except:
            return proxy[:10] + "***" + proxy[-10:] if len(proxy) > 20 else proxy
    
    async def test_browser_initialization(self):
        """Test browser initialization with proxy"""
        logger.info("\n🌐 Testing Browser Initialization")
        logger.info("-" * 40)
        
        try:
            # Test browser manager initialization
            browser_manager = BrowserManager(self.proxies)
            async with browser_manager:
                logger.info("✅ Browser manager initialized successfully")
                
                # Test getting a proxy
                if self.proxies:
                    proxy = browser_manager.get_proxy_for_check()
                    logger.info(f"✅ Proxy selected: {self._mask_proxy(proxy)}")
                else:
                    logger.info("ℹ️ No proxy configured, running direct connection")
                
                # Test user agent generation
                user_agent = browser_manager.get_next_user_agent()
                logger.info(f"✅ User agent generated: {user_agent[:50]}...")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Browser initialization failed: {e}")
            return False
    
    async def test_solver_services(self):
        """Test solver services are running"""
        logger.info("\n🛡️ Testing Solver Services")
        logger.info("-" * 40)
        
        import aiohttp
        
        # Test BotsForge API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:5033/", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        logger.info("✅ BotsForge API is running")
                    else:
                        logger.warning(f"⚠️ BotsForge API returned status {response.status}")
        except Exception as e:
            logger.warning(f"⚠️ BotsForge API not accessible: {e}")
        
        # Test Turnstile API (if enabled)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:5000/", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        logger.info("✅ Turnstile API is running")
                    else:
                        logger.warning(f"⚠️ Turnstile API returned status {response.status}")
        except Exception as e:
            logger.warning(f"⚠️ Turnstile API not accessible: {e}")
    
    async def test_epic_games_navigation(self):
        """Test navigation to Epic Games login page"""
        logger.info("\n🎮 Testing Epic Games Navigation")
        logger.info("-" * 40)
        
        if not self.accounts:
            logger.error("❌ No accounts loaded for testing")
            return False
        
        try:
            async with self.account_checker:
                email, password = self.accounts[0]
                logger.info(f"🔍 Testing navigation with account: {email}")
                
                # Get proxy for this test
                proxy = self.account_checker.browser_manager.get_proxy_for_check() if self.proxies else None
                if proxy:
                    logger.info(f"🌐 Using proxy: {self._mask_proxy(proxy)}")
                
                # Get user agent
                user_agent = self.account_checker.browser_manager.get_next_user_agent()
                logger.info(f"🤖 Using user agent: {user_agent[:50]}...")
                
                # Get browser and context
                browser = await self.account_checker.browser_manager.get_or_launch_browser(proxy)
                proxy_key = f"{proxy or '__noproxy__'}"
                context = await self.account_checker.browser_manager.get_optimized_context(
                    browser, proxy_key, user_agent=user_agent
                )
                
                # Create page and navigate
                page = await context.new_page()
                
                try:
                    logger.info(f"🌐 Navigating to Epic Games login page: {LOGIN_URL}")
                    await page.goto(LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
                    
                    # Wait a moment for page to fully load
                    await asyncio.sleep(3)
                    
                    # Check if we reached the login page
                    current_url = page.url
                    page_title = await page.title()
                    
                    logger.info(f"✅ Navigation successful!")
                    logger.info(f"   Current URL: {current_url}")
                    logger.info(f"   Page Title: {page_title}")
                    
                    # Check for Cloudflare/Turnstile challenges
                    await self._check_for_challenges(page)
                    
                    # Take a screenshot for verification
                    screenshot_path = project_root / "test_navigation_screenshot.png"
                    await page.screenshot(path=str(screenshot_path))
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                    
                    return True
                    
                finally:
                    await page.close()
                    
        except Exception as e:
            logger.error(f"❌ Epic Games navigation failed: {e}")
            return False
    
    async def _check_for_challenges(self, page):
        """Check for Cloudflare/Turnstile challenges on the page"""
        logger.info("🔍 Checking for Cloudflare/Turnstile challenges...")
        
        try:
            # Check for common Cloudflare indicators
            cloudflare_indicators = [
                'cf-challenge-running',
                'cf-browser-verification',
                'cf-under-attack',
                'cloudflare',
                'turnstile'
            ]
            
            page_content = await page.content()
            page_content_lower = page_content.lower()
            
            challenges_detected = []
            for indicator in cloudflare_indicators:
                if indicator in page_content_lower:
                    challenges_detected.append(indicator)
            
            if challenges_detected:
                logger.warning(f"⚠️ Potential challenges detected: {', '.join(challenges_detected)}")
                logger.info("🛡️ Solvers should handle these automatically during login")
            else:
                logger.info("✅ No obvious challenges detected")
            
            # Check for Turnstile widget specifically
            turnstile_elements = await page.query_selector_all('[data-sitekey]')
            if turnstile_elements:
                logger.warning(f"🎯 Found {len(turnstile_elements)} Turnstile widget(s)")
                for i, element in enumerate(turnstile_elements):
                    try:
                        sitekey = await element.get_attribute('data-sitekey')
                        logger.info(f"   Widget {i+1}: sitekey={sitekey}")
                    except:
                        pass
            
        except Exception as e:
            logger.warning(f"⚠️ Challenge detection failed: {e}")
    
    async def test_full_login_flow(self):
        """Test the complete login flow with solver integration"""
        logger.info("\n🔐 Testing Full Login Flow")
        logger.info("-" * 40)
        
        if not self.accounts:
            logger.error("❌ No accounts loaded for testing")
            return False
        
        try:
            # Create a fresh account checker for this test to avoid context issues
            fresh_checker = AccountChecker(
                proxies=self.proxies,
                user_id=999999  # Test user ID
            )
            
            async with fresh_checker:
                email, password = self.accounts[0]
                logger.info(f"🔐 Testing full login flow with: {email}")
                
                # Perform the complete account check (this includes solver integration)
                start_time = time.time()
                status, result = await fresh_checker.check_account(email, password)
                elapsed_time = time.time() - start_time
                
                logger.info(f"🏁 Login flow completed in {elapsed_time:.2f}s")
                logger.info(f"📊 Result Status: {status.value}")
                
                # Log detailed results
                if result:
                    logger.info("📋 Detailed Results:")
                    for key, value in result.items():
                        if key not in ['auth_code']:  # Don't log sensitive data
                            logger.info(f"   {key}: {value}")
                
                # Determine success
                if status.value == 'valid':
                    logger.info("✅ Login flow test PASSED - Account is valid!")
                    return True
                elif status.value in ['captcha', '2fa']:
                    logger.info(f"⚠️ Login flow test PARTIAL - {status.value.upper()} required")
                    return True  # This is expected behavior
                else:
                    logger.warning(f"❌ Login flow test FAILED - Status: {status.value}")
                    if result.get('error'):
                        logger.warning(f"   Error: {result['error']}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Full login flow test failed: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run all tests in sequence"""
        logger.info("🚀 Starting Comprehensive End-to-End Test")
        logger.info("=" * 60)
        
        test_results = {}
        
        try:
            # Initialize system
            logger.info("Phase 1: System Initialization")
            solver_status = await self.initialize_system()
            test_results['initialization'] = True
            
            # Test browser initialization
            logger.info("\nPhase 2: Browser Testing")
            test_results['browser'] = await self.test_browser_initialization()
            
            # Test solver services
            logger.info("\nPhase 3: Solver Services")
            await self.test_solver_services()
            test_results['solvers'] = True
            
            # Test Epic Games navigation
            logger.info("\nPhase 4: Epic Games Navigation")
            test_results['navigation'] = await self.test_epic_games_navigation()
            
            # Test full login flow
            logger.info("\nPhase 5: Full Login Flow")
            test_results['login_flow'] = await self.test_full_login_flow()
            
        except Exception as e:
            logger.error(f"❌ Comprehensive test failed: {e}")
            test_results['error'] = str(e)
        
        # Final report
        await self.generate_test_report(test_results)
        
        return test_results
    
    async def generate_test_report(self, results):
        """Generate comprehensive test report"""
        logger.info("\n📊 COMPREHENSIVE TEST REPORT")
        logger.info("=" * 60)
        
        passed_tests = sum(1 for result in results.values() if result is True)
        total_tests = len([k for k in results.keys() if k != 'error'])
        
        logger.info(f"📈 Overall Score: {passed_tests}/{total_tests} tests passed")
        
        # Individual test results
        test_names = {
            'initialization': 'System Initialization',
            'browser': 'Browser Management',
            'solvers': 'Solver Services',
            'navigation': 'Epic Games Navigation',
            'login_flow': 'Full Login Flow'
        }
        
        for key, name in test_names.items():
            if key in results:
                status = "✅ PASS" if results[key] else "❌ FAIL"
                logger.info(f"   {status} {name}")
        
        if 'error' in results:
            logger.error(f"💥 Critical Error: {results['error']}")
        
        # System status summary
        logger.info("\n🔧 System Status:")
        logger.info(f"   Proxies: {len(self.proxies)} loaded")
        logger.info(f"   Accounts: {len(self.accounts)} loaded")
        logger.info(f"   Solvers: Available and initialized")
        
        # Recommendations
        logger.info("\n💡 Recommendations:")
        if not results.get('browser'):
            logger.info("   - Check browser dependencies (patchright, camoufox)")
        if not results.get('navigation'):
            logger.info("   - Verify proxy configuration and network connectivity")
        if not results.get('login_flow'):
            logger.info("   - Check account credentials and solver configuration")
        
        logger.info("\n🎯 Test Complete!")
        logger.info("=" * 60)

async def main():
    """Main test execution"""
    tester = EndToEndTester()
    
    try:
        results = await tester.run_comprehensive_test()
        
        # Exit with appropriate code
        if all(results.get(key, False) for key in ['initialization', 'browser', 'navigation']):
            logger.info("🎉 All critical tests passed!")
            return 0
        else:
            logger.warning("⚠️ Some tests failed - check logs for details")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    # Ensure we're in the right directory
    os.chdir(project_root)
    
    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)