import asyncio
from time import time
import os
import random
import ctypes

try:
    from patchright.async_api import async_playwright
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    from playwright.async_api import async_playwright
    PATCHRIGHT_AVAILABLE = False
from loguru import logger
from dotenv import load_dotenv
from proxystr import Proxy
import cv2
import numpy as np

# Import display detector for proper headless/headed mode detection
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.display_detector import get_browser_config, has_display

# Handle pyautogui import with display detection
browser_config = get_browser_config()
PYAUTOGUI_AVAILABLE = False
pyautogui = None

if browser_config['can_use_pyautogui']:
    try:
        import pyautogui
        PYAUTOGUI_AVAILABLE = True
        logger.info("✅ PyAutoGUI available for visual interactions")
    except Exception as e:
        logger.warning(f"⚠️ PyAutoGUI not available: {e}")
        PYAUTOGUI_AVAILABLE = False
        pyautogui = None
else:
    logger.info("ℹ️ PyAutoGUI disabled - running in headless mode")

from .source import Singleton
from .models import CaptchaTask

load_dotenv()


class WindowGridManager:
    def __init__(self, window_width=500, window_height=200, vertical_overlap=60):
        self.window_width = window_width
        self.window_height = window_height
        self.vertical_step = window_height - vertical_overlap

        screen_width, screen_height = self.get_screen_size()
        self.cols = screen_width // window_width
        self.rows = screen_height // self.vertical_step

        self.grid = []
        self._generate_grid()

    @staticmethod
    def get_screen_size():
        # Use display detector for consistent screen size detection
        from utils.display_detector import get_display_detector
        return get_display_detector().get_screen_size()

    def _generate_grid(self):
        index = 0
        for row in range(self.rows):
            for col in range(self.cols):
                self.grid.append({
                    "id": index,
                    "x": col * self.window_width,
                    "y": row * self.vertical_step,
                    "is_occupied": False
                })
                index += 1

    def get_free_position(self):
        for pos in self.grid:
            if not pos["is_occupied"]:
                pos["is_occupied"] = True
                return pos
        raise RuntimeError("Нет свободных мест для окон.")

    def release_position(self, pos_id):
        for pos in self.grid:
            if pos["id"] == pos_id:
                pos["is_occupied"] = False
                return
        raise ValueError(f"Позиция {pos_id} не найдена.")

    def reset(self):
        for pos in self.grid:
            pos["is_occupied"] = False


class BrowserHandler:
    def __init__(self, proxy: str = None):
        self.playwright = None
        self.browser = None
        self.proxy = self.parse_proxy(proxy)
        self.window_manager = WindowGridManager()
        
        # Get display configuration
        self.browser_config = get_browser_config()
        self.headless_mode = self.browser_config['headless']
        self.can_position_windows = self.browser_config['can_position_windows']
        self.has_display = self.browser_config['has_display']
        
        logger.info(f"🖥️ BotsForge Browser mode: {'headless' if self.headless_mode else 'headed'}")
        logger.info(f"🖥️ Window positioning: {'enabled' if self.can_position_windows else 'disabled'}")
        logger.info(f"🖥️ PyAutoGUI available: {PYAUTOGUI_AVAILABLE}")
        if self.proxy:
            logger.info(f"🔗 Using proxy: {proxy}")

    def parse_proxy(self, proxy_str: str = None):
        """Parse proxy string for BotsForge solver"""
        if not proxy_str:
            # Fallback to environment variable if no proxy provided
            proxy_str = os.getenv('PROXY')
        
        if proxy_str:
            try:
                return Proxy(proxy_str).playwright
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse proxy '{proxy_str}': {e}")
                return None
        return None

    async def launch(self):
        self.playwright = await async_playwright().start()
        
        # Log which browser automation library is being used
        if PATCHRIGHT_AVAILABLE:
            logger.info("✅ BotsForge using Patchright for enhanced stealth")
        else:
            logger.info("⚠️ BotsForge using regular Playwright (Patchright not available)")
        
        # Try to use Camoufox first, fallback to Chromium
        try:
            from camoufox.async_api import AsyncCamoufox
            
            # Configure screen size based on display availability
            screen_size = f"{self.browser_config['screen_size'][0]}x{self.browser_config['screen_size'][1]}"
            
            self.browser = await AsyncCamoufox(
                headless=self.headless_mode,
                proxy=self.proxy,
                addons=[],
                os="windows",
                screen=screen_size,
                humanize=True
            ).start()
            logger.info(f"✅ Using Camoufox browser for BotsForge solver ({'headless' if self.headless_mode else 'headed'})")
        except Exception as e:
            logger.warning(f"⚠️ Failed to launch Camoufox, falling back to Chromium: {e}")
            
            # Configure args based on display availability
            args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
            
            # Add headless-specific optimizations
            if self.headless_mode:
                args.extend([
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',  # Save bandwidth in headless mode
                    '--disable-javascript-harmony-shipping',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows'
                ])
            
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless_mode,
                args=args,
                proxy=self.proxy
            )
            logger.info(f"✅ Using Chromium browser for BotsForge solver ({'headless' if self.headless_mode else 'headed'})")

    async def get_page(self):
        if not self.playwright or not self.browser:
            await self.launch()

        # Use mobile viewport for headless mode with dynamic mobile user agent
        from utils.user_agent_manager import get_user_agent
        
        context = await self.browser.new_context(
            viewport={"width": 375, "height": 812},  # iPhone X/11/12 size for mobile stealth
            user_agent=get_user_agent()
        )

        logger.debug(f"open page")
        page = await context.new_page()
        
        # Handle window positioning based on display availability
        position = self.window_manager.get_free_position()
        page._grid_position_id = position["id"]
        
        if self.can_position_windows and not self.headless_mode:
            # Only position windows if we have a display and not in headless mode
            try:
                await self.set_window_position(page, position["x"], position["y"])
                logger.debug(f"Window positioned at {position['x']}, {position['y']}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to position window: {e}")
        else:
            logger.debug(f"Virtual position assigned: {position['id']}")
        
        return page

    async def get_pages(self, amount: int = 1):
        if not self.playwright or not self.browser:
            await self.launch()

        pages = []
        for i in range(amount):
            from utils.user_agent_manager import get_user_agent
            
            context = await self.browser.new_context(
                viewport={"width": 375, "height": 812},  # iPhone X/11/12 size for mobile stealth
                user_agent=get_user_agent()
            )
            logger.debug(f"open page {i}")
            page = await context.new_page()
            
            # Handle window positioning based on display availability
            position = self.window_manager.get_free_position()
            page._grid_position_id = position["id"]
            
            if self.can_position_windows and not self.headless_mode:
                # Only position windows if we have a display and not in headless mode
                try:
                    await self.set_window_position(page, position["x"], position["y"])
                    logger.debug(f"Window {i} positioned at {position['x']}, {position['y']}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to position window {i}: {e}")
            else:
                logger.debug(f"Virtual position assigned to page {i}: {position['id']}")
            
            pages.append(page)
        return pages

    @staticmethod
    async def set_window_position(page, x, y):
        session = await page.context.new_cdp_session(page)
        # Получаем windowId
        result = await session.send("Browser.getWindowForTarget")
        window_id = result["windowId"]
        # Устанавливаем позицию
        await session.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {
                "left": x,
                "top": y,
                "width": 500,
                "height": 200
            }
        })

    async def close(self):
        try:
            await self.browser.close()
        except Exception:
            pass
        try:
            await self.playwright.stop()
        except Exception:
            pass

    async def close_page(self, page):
        self.window_manager.release_position(page._grid_position_id)
        await page.close()
        await page.context.close()


class Browser:
    def __init__(self, page=None, proxy: str = None):
        self.page = page
        self.proxy = proxy
        self.lock = asyncio.Lock()
        self.browser_handler = None

    async def solve_captcha(self, task: CaptchaTask):
        if not self.page:
            # Create browser handler with proxy support
            self.browser_handler = BrowserHandler(proxy=self.proxy)
            self.page = await self.browser_handler.get_page()

        async with self.lock:
            try:
                await self.block_rendering()
                await self.page.goto(task.websiteURL)
                await self.unblock_rendering()
                await self.load_captcha(websiteKey=task.websiteKey)
                return await self.wait_for_turnstile_token()
            finally:
                if self.browser_handler:
                    await self.browser_handler.close_page(self.page)
                self.page = None
                self.browser_handler = None

    async def antishadow_inject(self):
        await self.page.add_init_script("""
          (function() {
            const originalAttachShadow = Element.prototype.attachShadow;
            Element.prototype.attachShadow = function(init) {
              const shadow = originalAttachShadow.call(this, init);
              if (init.mode === 'closed') {
                window.__lastClosedShadowRoot = shadow;
              }
              return shadow;
            };
          })();
        """)

    async def load_captcha(self, websiteKey: str = '0x4AAAAAAA0SGzxWuGl6kriB', action: str = ''):
        script = f"""
        // 🧹 Удаляем предыдущую капчу, если есть
        const existing = document.querySelector('#captcha-overlay');
        if (existing) existing.remove();  // очистка предыдущего

        // 🔳 Создаём overlay
        const overlay = document.createElement('div');
        overlay.id = 'captcha-overlay';
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100vw';
        overlay.style.height = '100vh';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        overlay.style.display = 'block';
        overlay.style.justifyContent = 'center';
        overlay.style.alignItems = 'center';
        overlay.style.zIndex = '1000';

        // 🧩 Добавляем капчу
        const captchaDiv = document.createElement('div');
        captchaDiv.className = 'cf-turnstile';
        captchaDiv.setAttribute('data-sitekey', '{websiteKey}');
        captchaDiv.setAttribute('data-callback', 'onCaptchaSuccess');
        captchaDiv.setAttribute('data-action', '');

        overlay.appendChild(captchaDiv);
        document.body.appendChild(overlay);

        // 📜 Загружаем Cloudflare Turnstile
        const script = document.createElement('script');
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
        """

        # Выполняем скрипт в браузере через Selenium
        await self.page.evaluate(script)

    async def wait_for_turnstile_token(self) -> str | None:
        locator = self.page.locator('input[name="cf-turnstile-response"]')

        token = ""
        t = time()
        while not token:
            await asyncio.sleep(0.5)
            try:
                token = await locator.input_value(timeout=500)
                if await self.check_for_checkbox():
                    logger.debug('click checkbox')
            except Exception as er:
                logger.error(er)
                pass
            if token:
                logger.debug(f'got captcha token: {token}')
            if t + 15 < time():
                logger.warning('token not found')
                return None
        return token

    async def get_coords_to_click(self, x, y):
        # In headless mode, return the coordinates directly for Playwright clicking
        # Add small random offset for more human-like behavior
        return x + random.randint(-2, 2), y + random.randint(-2, 2)

    async def check_for_checkbox(self):
        """
        Enhanced checkbox detection that works in both headless and headed modes
        Priority: CSS selectors -> iframe detection -> visual detection (if available)
        """
        try:
            # Method 1: Try to find Turnstile checkbox using CSS selectors (most reliable)
            turnstile_selectors = [
                'input[type="checkbox"][data-cf-turnstile]',
                'input[data-cf-turnstile]',
                '.cf-turnstile input',
                '[data-sitekey] input',
                'iframe[src*="challenges.cloudflare.com"]',
                'iframe[src*="turnstile"]'
            ]
            
            for selector in turnstile_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    try:
                        if selector.startswith('iframe'):
                            # Handle iframe case
                            box = await element.bounding_box()
                            if box:
                                center_x = box['x'] + box['width'] / 2
                                center_y = box['y'] + box['height'] / 2
                                await self.human_click(center_x, center_y)
                                logger.debug(f"Found and clicked Turnstile iframe using selector: {selector}")
                                return True
                        else:
                            # Handle input element case
                            await element.click()
                            logger.debug(f"Found and clicked Turnstile checkbox using selector: {selector}")
                            return True
                    except Exception as e:
                        logger.debug(f"Failed to click element with selector {selector}: {e}")
                        continue
            
            # Method 2: Try to find any iframe with Turnstile-related content
            iframes = await self.page.query_selector_all('iframe')
            for iframe in iframes:
                try:
                    src = await iframe.get_attribute('src')
                    if src and ('challenges.cloudflare.com' in src or 'turnstile' in src):
                        box = await iframe.bounding_box()
                        if box:
                            center_x = box['x'] + box['width'] / 2
                            center_y = box['y'] + box['height'] / 2
                            await self.human_click(center_x, center_y)
                            logger.debug("Found and clicked Turnstile iframe by src inspection")
                            return True
                except Exception as e:
                    logger.debug(f"Error inspecting iframe: {e}")
                    continue
            
            # Method 3: Visual detection with OpenCV (fallback for complex cases)
            # Only use visual detection if we have the capability
            if self._should_use_visual_detection():
                return await self._visual_checkbox_detection()
                
        except Exception as e:
            logger.error(f"Error in checkbox detection: {e}")
            
        return False
    
    def _should_use_visual_detection(self) -> bool:
        """Determine if visual detection should be used"""
        # Use visual detection if:
        # 1. We have a display (for PyAutoGUI if needed)
        # 2. OR we're in headless mode but can still do screenshot-based detection
        browser_config = get_browser_config()
        return True  # OpenCV-based detection works in both headless and headed modes
    
    async def _visual_checkbox_detection(self) -> bool:
        """Visual checkbox detection using OpenCV"""
        try:
            # Take screenshot for analysis
            image_bytes = await self.page.screenshot(full_page=True)
            
            # Convert for OpenCV
            screen_np = np.frombuffer(image_bytes, dtype=np.uint8)
            screen = cv2.imdecode(screen_np, cv2.IMREAD_COLOR)
            
            # Load template with fallback
            template_path = os.path.join(os.path.dirname(__file__), "screens", "checkbox.png")
            if not os.path.exists(template_path):
                os.makedirs(os.path.dirname(template_path), exist_ok=True)
                logger.debug("Checkbox template not found, skipping visual detection")
                return False
                
            template = cv2.imread(template_path)
            if template is None:
                logger.debug("Failed to load checkbox template")
                return False
            
            # Template matching
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.8:  # Slightly lower threshold for better detection
                logger.debug(f"Visual checkbox detection successful! Confidence: {max_val:.3f}")
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                
                # Get adjusted coordinates for clicking
                x, y = await self.get_coords_to_click(center_x, center_y)
                
                # Perform human-like click
                await self.human_click(x, y)
                
                logger.debug(f"Clicked checkbox at coordinates: {x}, {y}")
                return True
            else:
                logger.debug(f"Visual checkbox detection failed. Best match confidence: {max_val:.3f}")
                
        except Exception as e:
            logger.error(f"Error in visual checkbox detection: {e}")
            
        return False

    @staticmethod
    async def human_like_mouse_move(page, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 25):
        """Двигает мышь по кривой с шумом"""
        await page.mouse.move(start_x, start_y)
        for i in range(1, steps + 1):
            progress = i / steps
            x_noise = random.uniform(-1, 1)
            y_noise = random.uniform(-1, 1)
            x = start_x + (end_x - start_x) * progress + x_noise
            y = start_y + (end_y - start_y) * progress + y_noise
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.02))

    async def human_click(self, x: int, y: int):
        page = self.page
        """Реалистичный человекоподобный клик по координатам (x, y)"""
        # Получим текущую позицию мыши (грубо, начнем с (0,0) если не знаем)
        try:
            # Эвристика — просто двигай мышь в левый верхний угол перед началом
            await page.mouse.move(0, 0)
        except Exception:
            pass

        # Подобие дрожащей руки: движение к цели с флуктуациями
        await self.human_like_mouse_move(page, 0, 0, x, y, steps=random.randint(15, 30))

        # Маленькая задержка перед нажатием (реакция человека)
        await asyncio.sleep(random.uniform(0.05, 0.15))

        # Клик: нажатие, задержка и отпускание
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.12))
        await page.mouse.up()

        # После клика мышь может немного дрогнуть
        if random.random() < 0.4:
            await page.mouse.move(x + random.randint(-3, 3), y + random.randint(-3, 3))

    async def route_handler(browser, route):
        blocked_extensions = ['.js', '.css', '.png', '.jpg', '.svg', '.gif', '.woff', '.ttf']

        # print(route, request)
        if any(route.request.url.endswith(ext) for ext in blocked_extensions):
            await route.abort()
        else:
            await route.continue_()

    async def block_rendering(self):
        await self.page.route("**/*", self.route_handler)

    async def unblock_rendering(self):
        await self.page.unroute("**/*", self.route_handler)
