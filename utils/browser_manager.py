"""
Browser management module for Epic Games account checking
Handles browser initialization, context management, and proxy configuration
Enhanced with resource monitoring and leak prevention
"""
import asyncio
import logging
import random
import psutil
import gc
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

from config.settings import (
    HEADLESS, 
    NAVIGATION_TIMEOUT, 
    MAX_CONCURRENT_CHECKS,
    BLOCK_RESOURCE_TYPES,
    BROWSER_SLOWMO,
    USE_ENHANCED_BROWSER,
    PREFERRED_BROWSER_TYPE,
    DEBUG_ENHANCED_FEATURES,
    MAX_CONTEXTS_PER_BROWSER,
    CONTEXT_REUSE_COUNT,
    CLEANUP_INTERVAL,
    MEMORY_THRESHOLD_MB,
    MAX_BROWSER_AGE_SECONDS,
    RESOURCE_CHECK_INTERVAL,
    ENABLE_RESOURCE_MONITORING
)

logger = logging.getLogger(__name__)

try:
    from patchright.async_api import async_playwright as patchright_async
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    PATCHRIGHT_AVAILABLE = False
    logger.error("Patchright not available - enhanced browser required!")

try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    logger.warning("Camoufox not available, using Chromium-based browsers only")


class BrowserManager:
    """Manages browser instances, contexts, and proxy configurations with enhanced resource monitoring"""
    
    def __init__(self, proxies: List[str] = None):
        self.proxies = proxies or []
        self.playwright = None
        self.browser_pool: Dict[str, Any] = {}
        self.context_pool: Dict[str, List[Any]] = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        
        # Performance optimization settings
        self.max_contexts_per_browser = MAX_CONTEXTS_PER_BROWSER
        self.context_reuse_count = CONTEXT_REUSE_COUNT
        self.context_usage_counter: Dict[str, int] = {}
        self.cleanup_interval = CLEANUP_INTERVAL
        self.checks_performed = 0
        
        # Single proxy handling
        self.single_proxy_mode = len(self.proxies) == 1
        self.current_proxy_index = 0
        
        # User agent management - use centralized manager
        from utils.user_agent_manager import user_agent_manager
        self.user_agent_manager = user_agent_manager
        self._ua_toggle = True
        
        # Resource monitoring
        self.process = psutil.Process() if ENABLE_RESOURCE_MONITORING else None
        self.initial_memory = (self.process.memory_info().rss / 1024 / 1024 
                              if self.process else 0)  # MB
        self.last_cleanup_time = time.time()
        self.resource_check_interval = RESOURCE_CHECK_INTERVAL
        self.memory_threshold_mb = MEMORY_THRESHOLD_MB
        self.max_browser_age_seconds = MAX_BROWSER_AGE_SECONDS
        self.browser_creation_times: Dict[str, float] = {}
    
    async def __aenter__(self):
        """Initialize enhanced browser automation"""
        if DEBUG_ENHANCED_FEATURES:
            logger.info("🚀 Initializing enhanced browser automation")
        
        if PATCHRIGHT_AVAILABLE:
            self.playwright = await patchright_async().start()
            if DEBUG_ENHANCED_FEATURES:
                logger.info("✅ Using Patchright for enhanced stealth")
        else:
            # Fallback to regular playwright if available
            try:
                from playwright.async_api import async_playwright
                self.playwright = await async_playwright().start()
                logger.info("⚠️ Using regular Playwright (Patchright not available)")
            except ImportError:
                raise RuntimeError("Neither Patchright nor Playwright is available!")
        
        return self
    
    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Clean up browsers and Playwright"""
        for browser in self.browser_pool.values():
            try:
                await browser.close()
            except Exception:
                pass
        
        if self.playwright:
            await self.playwright.stop()
    
    def get_resource_usage(self) -> Dict[str, float]:
        """Get current resource usage statistics"""
        try:
            if not self.process:
                return {
                    'browser_count': len(self.browser_pool),
                    'total_contexts': sum(len(contexts) for contexts in self.context_pool.values()),
                    'checks_performed': self.checks_performed
                }
            
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent()
            
            return {
                'memory_mb': memory_info.rss / 1024 / 1024,
                'memory_growth_mb': (memory_info.rss / 1024 / 1024) - self.initial_memory,
                'cpu_percent': cpu_percent,
                'browser_count': len(self.browser_pool),
                'total_contexts': sum(len(contexts) for contexts in self.context_pool.values()),
                'checks_performed': self.checks_performed
            }
        except Exception as e:
            logger.warning(f"⚠️ Error getting resource usage: {e}")
            return {
                'browser_count': len(self.browser_pool),
                'total_contexts': sum(len(contexts) for contexts in self.context_pool.values()),
                'checks_performed': self.checks_performed
            }
    
    def should_force_cleanup(self) -> bool:
        """Determine if we should force cleanup based on resource usage"""
        try:
            time_since_cleanup = time.time() - self.last_cleanup_time
            
            # Always check time-based cleanup
            if (time_since_cleanup > 60 or  # Force cleanup every minute
                self.checks_performed % self.resource_check_interval == 0):
                return True
            
            # Check memory-based cleanup if monitoring is enabled
            if self.process:
                current_memory = self.process.memory_info().rss / 1024 / 1024
                return current_memory > self.memory_threshold_mb
            
            return False
        except Exception:
            return False
    
    async def cleanup_old_browsers(self):
        """Clean up browsers that are too old"""
        current_time = time.time()
        browsers_to_remove = []
        
        for proxy_key, creation_time in self.browser_creation_times.items():
            if current_time - creation_time > self.max_browser_age_seconds:
                browsers_to_remove.append(proxy_key)
        
        for proxy_key in browsers_to_remove:
            if proxy_key in self.browser_pool:
                try:
                    browser = self.browser_pool[proxy_key]
                    await browser.close()
                    del self.browser_pool[proxy_key]
                    del self.browser_creation_times[proxy_key]
                    
                    # Also clean up associated contexts
                    if proxy_key in self.context_pool:
                        del self.context_pool[proxy_key]
                    
                    if DEBUG_ENHANCED_FEATURES:
                        logger.info(f"🧹 Closed old browser: {proxy_key}")
                except Exception as e:
                    logger.warning(f"⚠️ Error closing old browser {proxy_key}: {e}")
    
    def get_next_user_agent(self) -> str:
        """Get next user agent string, rotating between Android and iPhone mobiles"""
        # Use centralized user agent manager with alternating preference
        prefer_android = self._ua_toggle
        self._ua_toggle = not self._ua_toggle
        
        return self.user_agent_manager.get_mobile_user_agent(prefer_android=prefer_android)
    
    def get_proxy_for_check(self) -> Optional[str]:
        """Get proxy for account check with optimized single proxy handling"""
        if not self.proxies:
            return None
        
        if self.single_proxy_mode:
            return self.proxies[0]
        else:
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            return proxy
    
    def parse_proxy_for_playwright(self, proxy_line: str) -> Optional[Dict[str, str]]:
        """Parse proxy string into Playwright proxy format"""
        if not proxy_line:
            return None
        
        try:
            if '://' not in proxy_line:
                proxy_line = f"http://{proxy_line}"
            
            parsed = urlparse(proxy_line)
            scheme = parsed.scheme.lower()
            
            # Handle SOCKS5 with authentication issue
            if scheme == 'socks5' and parsed.username and parsed.password:
                logger.info(f"⚠️ SOCKS5 with auth not supported by Chromium, converting to HTTP")
                scheme = "http"
            elif scheme not in ['http', 'https', 'socks5']:
                logger.info(f"⚠️ Unsupported proxy scheme '{scheme}', defaulting to http")
                scheme = "http"
            
            proxy_dict = {
                "server": f"{scheme}://{parsed.hostname}:{parsed.port}"
            }
            
            if parsed.username and parsed.password:
                if scheme in ['http', 'https']:
                    proxy_dict["username"] = parsed.username
                    proxy_dict["password"] = parsed.password
                elif scheme == 'socks5':
                    logger.info(f"⚠️ SOCKS5 authentication not supported, proxy may not work")
            
            logger.info(f"🔧 Parsed proxy: {scheme}://{parsed.hostname}:{parsed.port} (auth: {'yes' if parsed.username and scheme != 'socks5' else 'no'})")
            return proxy_dict
            
        except Exception as e:
            logger.info(f"❌ Error parsing proxy {proxy_line}: {e}")
            return None
    
    async def get_or_launch_browser(self, proxy_line: Optional[str]) -> Any:
        """Get or launch browser with enhanced capabilities"""
        proxy_key = f"{proxy_line or '__noproxy__'}_{PREFERRED_BROWSER_TYPE}"
        
        if proxy_key in self.browser_pool:
            return self.browser_pool[proxy_key]
        
        proxy_dict = None
        if proxy_line:
            proxy_dict = self.parse_proxy_for_playwright(proxy_line)
        
        # Cloudflare-friendly browser launch arguments
        # Removed args that interfere with JavaScript/WebGL/Canvas execution
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-component-extensions-with-background-pages",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-field-trial-config",
            "--disable-back-forward-cache",
            "--disable-background-networking",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--disable-background-media-suspend",
            "--disable-translate",
            "--disable-ipc-flooding-protection",
            "--no-default-browser-check",
            "--no-first-run",
            "--no-pings",
            "--no-service-autorun",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-client-side-phishing-detection",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-sync",
            "--allow-running-insecure-content",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            # Enable JavaScript execution and WebGL for Cloudflare challenges
            "--enable-javascript",
            "--enable-webgl",
            "--enable-accelerated-2d-canvas",
            "--enable-gpu-rasterization",
            # Keep essential security features while allowing challenge execution
            "--disable-features=VizDisplayCompositor,TranslateUI"
        ]
        
        # Launch browser based on preference
        if PREFERRED_BROWSER_TYPE == "camoufox" and CAMOUFOX_AVAILABLE:
            try:
                # Create Camoufox configuration with proper types
                camoufox_config = {
                    'headless': HEADLESS,
                    'addons': [],
                    'humanize': True,
                    'geoip': True  # Enable GeoIP for better proxy handling
                }
                
                # Add proxy if available
                if proxy_dict:
                    camoufox_config['proxy'] = proxy_dict
                
                camoufox_browser = AsyncCamoufox(**camoufox_config)
                browser = await camoufox_browser.start()
                
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"🦊 Launched Camoufox browser with proxy: {proxy_line or 'None'}")
                
            except Exception as e:
                logger.info(f"❌ Failed to launch Camoufox: {e}, falling back to Chromium")
                browser = await self.playwright.chromium.launch(
                    headless=HEADLESS,
                    proxy=proxy_dict,
                    args=browser_args,
                    slow_mo=BROWSER_SLOWMO
                )
        else:
            browser = await self.playwright.chromium.launch(
                headless=HEADLESS,
                proxy=proxy_dict,
                args=browser_args,
                slow_mo=BROWSER_SLOWMO
            )
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🌐 Launched Chromium browser with proxy: {proxy_line or 'None'}")
        
        self.browser_pool[proxy_key] = browser
        self.browser_creation_times[proxy_key] = time.time()
        return browser
    
    async def create_visible_browser_for_challenges(self, proxy: Optional[str] = None) -> Any:
        """Create a visible (non-headless) browser specifically for solving challenges"""
        logger.info("🔧 Creating visible browser for challenge solving...")
        
        # Set up virtual display for headless environments
        from utils.virtual_display import ensure_virtual_display
        if not ensure_virtual_display():
            logger.warning("⚠️ Failed to start virtual display, falling back to headless mode")
        else:
            logger.info("✅ Virtual display ready for visible browser")
        
        proxy_dict = None
        if proxy:
            proxy_dict = self.parse_proxy(proxy)
        
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--no-first-run',
            '--no-zygote',
            '--window-size=1280,720',  # Set a reasonable window size
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-blink-features=AutomationControlled',  # Hide automation
            '--disable-extensions-except',
            '--disable-plugins-discovery',
            '--no-default-browser-check',
            '--no-first-run',
            '--disable-default-apps'
        ]
        
        # Launch browser in visible mode (headless=False)
        if PREFERRED_BROWSER_TYPE == "camoufox" and CAMOUFOX_AVAILABLE:
            try:
                camoufox_config = {
                    'headless': False,  # Force visible mode
                    'addons': [],
                    'humanize': True,
                    'geoip': True
                }
                
                if proxy_dict:
                    camoufox_config['proxy'] = proxy_dict
                
                browser = AsyncCamoufox(**camoufox_config)
                await browser.launch()
                logger.info("🦊 Launched visible Camoufox browser for challenge solving")
                return browser
                
            except Exception as e:
                logger.warning(f"❌ Failed to launch visible Camoufox: {e}, falling back to Chromium")
        
        # Fallback to visible Chromium
        browser = await self.playwright.chromium.launch(
            headless=False,  # Force visible mode
            proxy=proxy_dict,
            args=browser_args,
            slow_mo=BROWSER_SLOWMO
        )
        logger.info("🌐 Launched visible Chromium browser for challenge solving")
        return browser
    
    async def new_context(self, browser: Any, user_agent: str = None, force_visible: bool = False) -> Any:
        """Create new browser context with stealth settings"""
        if user_agent is None:
            user_agent = self.get_next_user_agent()
        
        # Use desktop viewports for better Turnstile widget support
        # Mobile viewports can cause issues with Turnstile widget rendering
        desktop_viewports = [
            {"width": 1280, "height": 720},   # Standard HD
            {"width": 1366, "height": 768},   # Common laptop
            {"width": 1920, "height": 1080},  # Full HD
            {"width": 1440, "height": 900},   # MacBook Pro 15"
            {"width": 1536, "height": 864},   # Surface Pro
        ]
        viewport = random.choice(desktop_viewports)
        
        context = await browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation", "notifications"],
            java_script_enabled=True,  # Explicitly enable JavaScript
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        
        # Enhanced stealth JavaScript with Turnstile support
        await context.add_init_script("""
            // Basic stealth
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Ensure proper window dimensions for Turnstile
            Object.defineProperty(window, 'outerWidth', {
                get: () => window.innerWidth,
            });
            
            Object.defineProperty(window, 'outerHeight', {
                get: () => window.innerHeight,
            });
            
            // Ensure document is ready for Turnstile widgets
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    console.log('DOM ready for Turnstile widgets');
                });
            }
            
            // Add visibility API support for Turnstile
            Object.defineProperty(document, 'hidden', {
                get: () => false,
            });
            
            Object.defineProperty(document, 'visibilityState', {
                get: () => 'visible',
            });
            
            Object.defineProperty(navigator, 'serviceWorker', {
                get: () => ({
                    register: () => Promise.resolve(),
                    getRegistrations: () => Promise.resolve([]),
                    ready: Promise.resolve({
                        unregister: () => Promise.resolve(true),
                        update: () => Promise.resolve(),
                        pushManager: {
                            subscribe: () => Promise.resolve(),
                            getSubscription: () => Promise.resolve(null)
                        },
                        sync: {
                            register: () => Promise.resolve()
                        },
                        active: {
                            postMessage: () => {},
                            terminate: () => {}
                        },
                        installing: null,
                        waiting: null,
                        onupdatefound: null,
                        oncontrollerchange: null,
                        onmessage: null
                    }),
                    controller: null,
                    oncontrollerchange: null,
                    onmessage: null
                })
            });

            // PROACTIVE SITEKEY EXTRACTION - Capture sitekeys as they appear
            window._capturedTurnstileData = {
                sitekeys: new Set(),
                parameters: {},
                widgets: [],
                scripts: []
            };

            // Monitor DOM mutations for Turnstile elements
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1) { // Element node
                            // Check the added element itself
                            checkElementForTurnstile(node);
                            // Check all descendants
                            const descendants = node.querySelectorAll ? node.querySelectorAll('*') : [];
                            descendants.forEach(checkElementForTurnstile);
                        }
                    });
                });
            });

            function checkElementForTurnstile(element) {
                if (!element.getAttribute) return;
                
                // Check for sitekey attributes
                const sitekeyAttrs = ['data-sitekey', 'data-cf-turnstile-sitekey', 'data-turnstile-sitekey', 'sitekey'];
                sitekeyAttrs.forEach(attr => {
                    const value = element.getAttribute(attr);
                    if (value && value.length > 10) {
                        window._capturedTurnstileData.sitekeys.add(value);
                        window._capturedTurnstileData.parameters[value] = {
                            sitekey: value,
                            action: element.getAttribute('data-action'),
                            cdata: element.getAttribute('data-cdata'),
                            pagedata: element.getAttribute('data-chl-page-data'),
                            element: element.tagName + (element.className ? '.' + element.className : '')
                        };
                    }
                });

                // Check for Turnstile widgets
                if (element.classList && (element.classList.contains('cf-turnstile') || element.classList.contains('turnstile-widget'))) {
                    window._capturedTurnstileData.widgets.push({
                        element: element,
                        attributes: Array.from(element.attributes).reduce((acc, attr) => {
                            acc[attr.name] = attr.value;
                            return acc;
                        }, {})
                    });
                }
            }

            // Start observing immediately
            if (document.body) {
                observer.observe(document.body, { childList: true, subtree: true });
            } else {
                document.addEventListener('DOMContentLoaded', () => {
                    observer.observe(document.body, { childList: true, subtree: true });
                });
            }

            // Monitor script additions for Turnstile configuration
            const originalAppendChild = Element.prototype.appendChild;
            Element.prototype.appendChild = function(child) {
                if (child.tagName === 'SCRIPT') {
                    const content = child.textContent || child.innerHTML;
                    if (content && (content.includes('turnstile') || content.includes('cf-turnstile') || content.includes('sitekey'))) {
                        window._capturedTurnstileData.scripts.push({
                            content: content,
                            src: child.src || null,
                            timestamp: Date.now()
                        });
                        
                        // Extract sitekeys from script content
                        const sitekeyPatterns = [
                            /sitekey['"\\s]*[:=]['"\\s]*([0-9a-zA-Z_-]{10,})/g,
                            /"sitekey"\\s*:\\s*"([^"]+)"/g,
                            /'sitekey'\\s*:\\s*'([^']+)'/g
                        ];
                        
                        sitekeyPatterns.forEach(pattern => {
                            let match;
                            while ((match = pattern.exec(content)) !== null) {
                                if (match[1] && match[1].length > 10) {
                                    window._capturedTurnstileData.sitekeys.add(match[1]);
                                }
                            }
                        });
                    }
                }
                return originalAppendChild.call(this, child);
            };

            // Monitor window object changes for Turnstile variables
            const checkWindowVars = () => {
                // Check for Turnstile configuration
                if (window.turnstile) {
                    if (window.turnstile.sitekey) {
                        window._capturedTurnstileData.sitekeys.add(window.turnstile.sitekey);
                    }
                    if (window.turnstile._widgets) {
                        Object.values(window.turnstile._widgets).forEach(widget => {
                            if (widget.sitekey) {
                                window._capturedTurnstileData.sitekeys.add(widget.sitekey);
                            }
                        });
                    }
                }

                // Check for Cloudflare configuration
                if (window.cf && window.cf.sitekey) {
                    window._capturedTurnstileData.sitekeys.add(window.cf.sitekey);
                }

                // Check for Cloudflare challenge options
                if (window._cf_chl_opt) {
                    ['sitekey', 'cSitekey', 'turnstileSitekey'].forEach(key => {
                        if (window._cf_chl_opt[key]) {
                            window._capturedTurnstileData.sitekeys.add(window._cf_chl_opt[key]);
                        }
                    });
                }
            };

            // Check window variables periodically
            setInterval(checkWindowVars, 500);
            
            // Check immediately if DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', checkWindowVars);
            } else {
                checkWindowVars();
            }

            console.log('🔍 Proactive Turnstile sitekey extraction initialized');

            // CRITICAL: 2captcha-required JavaScript injection for Cloudflare Challenge pages
            // This intercepts turnstile.render calls to capture cData, chlPageData, and action
            const turnstileInterceptor = setInterval(() => {
                if (window.turnstile) {
                    clearInterval(turnstileInterceptor);
                    
                    // Store original render function
                    const originalRender = window.turnstile.render;
                    
                    // Override turnstile.render to capture parameters
                    window.turnstile.render = function(container, params) {
                        console.log('🎯 Turnstile render intercepted!');
                        
                        // Capture all parameters for 2captcha API
                        const capturedParams = {
                            type: "TurnstileTaskProxyless",
                            websiteKey: params.sitekey,
                            websiteURL: window.location.href,
                            data: params.cData,
                            pagedata: params.chlPageData,
                            action: params.action,
                            userAgent: navigator.userAgent
                        };
                        
                        // Store parameters globally for extraction
                        window._capturedTurnstileData.challengeParams = capturedParams;
                        window._capturedTurnstileData.sitekeys.add(params.sitekey);
                        window._capturedTurnstileData.parameters[params.sitekey] = {
                            sitekey: params.sitekey,
                            action: params.action,
                            cdata: params.cData,
                            pagedata: params.chlPageData,
                            source: 'render_intercept'
                        };
                        
                        // Store callback for later use
                        if (params.callback) {
                            window.tsCallback = params.callback;
                        }
                        
                        console.log('📋 Captured Turnstile parameters:', JSON.stringify(capturedParams));
                        
                        // Return a dummy widget ID (2captcha requirement)
                        return 'intercepted_widget_' + Date.now();
                    };
                    
                    console.log('✅ Turnstile render function intercepted for Cloudflare Challenge pages');
                }
            }, 10);

            // Also intercept any dynamic script loading of Turnstile API
            const originalCreateElement = document.createElement;
            document.createElement = function(tagName) {
                const element = originalCreateElement.call(this, tagName);
                
                if (tagName.toLowerCase() === 'script') {
                    const originalSetSrc = Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, 'src').set;
                    Object.defineProperty(element, 'src', {
                        set: function(value) {
                            if (value && value.includes('challenges.cloudflare.com/turnstile')) {
                                console.log('🔍 Turnstile API script detected:', value);
                                // Let the script load normally, our interceptor will handle it
                            }
                            originalSetSrc.call(this, value);
                        },
                        get: function() {
                            return this.getAttribute('src');
                        }
                    });
                }
                
                return element;
            };
        """)
        
        # Block unnecessary resources for performance
        if BLOCK_RESOURCE_TYPES:
            await context.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
                else route.continue_()
            ))
        
        return context
    
    async def get_optimized_context(self, browser: Any, proxy_key: str, user_agent: str = None) -> Any:
        """Get a completely fresh browser context for maximum isolation"""
        if self.context_reuse_count <= 1:
            context = await self.new_context(browser, user_agent=user_agent)
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🆕 Created fresh isolated context for {proxy_key}")
            return context
        
        # Legacy reuse logic (only if CONTEXT_REUSE_COUNT > 1)
        if proxy_key not in self.context_pool:
            self.context_pool[proxy_key] = []
        
        contexts = self.context_pool[proxy_key]
        for i, context in enumerate(contexts):
            context_key = f"{proxy_key}_{i}"
            usage_count = self.context_usage_counter.get(context_key, 0)
            
            if usage_count < self.context_reuse_count:
                await self.clear_context_session(context)
                self.context_usage_counter[context_key] = usage_count + 1
                if DEBUG_ENHANCED_FEATURES:
                    logger.info(f"🔄 Reusing context {context_key} (usage: {usage_count + 1}/{self.context_reuse_count}) - Session cleared")
                return context
        
        if len(contexts) < self.max_contexts_per_browser:
            context = await self.new_context(browser, user_agent=user_agent)
            contexts.append(context)
            context_key = f"{proxy_key}_{len(contexts) - 1}"
            self.context_usage_counter[context_key] = 1
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"🆕 Created new context {context_key}")
            return context
        
        # Replace oldest context if at max capacity
        old_context = contexts[0]
        try:
            await old_context.close()
        except:
            pass
        
        new_context = await self.new_context(browser, user_agent=user_agent)
        contexts[0] = new_context
        context_key = f"{proxy_key}_0"
        self.context_usage_counter[context_key] = 1
        
        if DEBUG_ENHANCED_FEATURES:
            logger.info(f"🔄 Replaced oldest context {context_key}")
        return new_context
    
    async def clear_context_session(self, context: Any):
        """Clear all session data from context to ensure clean state"""
        try:
            await context.clear_cookies()
            
            for page in context.pages:
                try:
                    await page.evaluate("() => { localStorage.clear(); }")
                    await page.evaluate("() => { sessionStorage.clear(); }")
                    await page.evaluate("() => { if (window.caches) { caches.keys().then(names => names.forEach(name => caches.delete(name))); } }")
                except:
                    pass
            
            if DEBUG_ENHANCED_FEATURES:
                logger.info("🧹 Context session cleared - cookies, localStorage, sessionStorage")
                
        except Exception as e:
            if DEBUG_ENHANCED_FEATURES:
                logger.info(f"⚠️ Error clearing context session: {e}")
            pass
    
    async def cleanup_old_contexts(self, force: bool = False):
        """Enhanced cleanup with resource monitoring and leak prevention"""
        should_cleanup = (force or 
                         self.checks_performed % self.cleanup_interval == 0 or 
                         self.should_force_cleanup())
        
        if not should_cleanup:
            return
        
        # Get resource usage before cleanup
        resources_before = self.get_resource_usage()
        
        if DEBUG_ENHANCED_FEATURES or resources_before.get('memory_mb', 0) > 500:
            logger.info(f"🧹 Performing enhanced cleanup (checks: {self.checks_performed})")
            logger.info(f"   Memory: {resources_before.get('memory_mb', 0):.1f}MB "
                       f"(+{resources_before.get('memory_growth_mb', 0):.1f}MB)")
            logger.info(f"   Browsers: {resources_before.get('browser_count', 0)}, "
                       f"Contexts: {resources_before.get('total_contexts', 0)}")
        
        contexts_cleaned = 0
        browsers_cleaned = 0
        
        # Clean up old browsers first
        await self.cleanup_old_browsers()
        
        # Clean up contexts more aggressively if memory is high
        memory_pressure = resources_before.get('memory_mb', 0) > self.memory_threshold_mb
        
        for proxy_key, contexts in list(self.context_pool.items()):
            if memory_pressure:
                # Under memory pressure, close all contexts
                for context in contexts:
                    try:
                        await context.close()
                        contexts_cleaned += 1
                    except:
                        pass
                self.context_pool[proxy_key] = []
            elif len(contexts) > self.max_contexts_per_browser:
                # Normal cleanup - keep only the newest contexts
                old_contexts = contexts[:-self.max_contexts_per_browser]
                self.context_pool[proxy_key] = contexts[-self.max_contexts_per_browser:]
                
                for context in old_contexts:
                    try:
                        await context.close()
                        contexts_cleaned += 1
                    except:
                        pass
        
        # Clean up usage counters for removed contexts
        valid_keys = set()
        for pk in self.context_pool.keys():
            for i in range(len(self.context_pool[pk])):
                valid_keys.add(f"{pk}_{i}")
        
        for key in list(self.context_usage_counter.keys()):
            if key not in valid_keys:
                del self.context_usage_counter[key]
        
        # Force garbage collection if under memory pressure
        if memory_pressure:
            gc.collect()
            logger.info("🧹 Forced garbage collection due to memory pressure")
        
        # Update cleanup time
        self.last_cleanup_time = time.time()
        
        # Log cleanup results
        if contexts_cleaned > 0 or browsers_cleaned > 0 or DEBUG_ENHANCED_FEATURES:
            resources_after = self.get_resource_usage()
            memory_freed = resources_before.get('memory_mb', 0) - resources_after.get('memory_mb', 0)
            
            logger.info(f"🧹 Cleanup complete: {contexts_cleaned} contexts, {browsers_cleaned} browsers")
            if memory_freed > 0:
                logger.info(f"   Memory freed: {memory_freed:.1f}MB")
            logger.info(f"   Current memory: {resources_after.get('memory_mb', 0):.1f}MB")