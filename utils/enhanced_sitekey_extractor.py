"""
Enhanced Sitekey Extractor for Cloudflare/Turnstile Challenges
This module provides comprehensive sitekey extraction methods
"""
import asyncio
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

class EnhancedSitekeyExtractor:
    """Enhanced sitekey extraction for Cloudflare/Turnstile challenges"""
    
    # NO HARDCODED SITEKEYS - Each challenge has its own unique sitekey
    # We must extract the actual sitekey from the current page/challenge
    
    @staticmethod
    async def extract_sitekey_comprehensive(page) -> Optional[str]:
        """
        Comprehensive sitekey extraction using multiple methods
        """
        try:
            logger.info("🔍 Starting comprehensive sitekey extraction...")
            
            # Method 1: Direct element attribute extraction
            sitekey = await EnhancedSitekeyExtractor._extract_from_elements(page)
            if sitekey:
                logger.info(f"✅ Sitekey found via element attributes: {sitekey}")
                return sitekey
            
            # Method 1.5: Cloudflare specific challenge page extraction
            sitekey = await EnhancedSitekeyExtractor._extract_from_cloudflare_challenge(page)
            if sitekey:
                logger.info(f"✅ Sitekey found in Cloudflare challenge: {sitekey}")
                return sitekey
            
            # Method 2: JavaScript execution to find sitekey
            sitekey = await EnhancedSitekeyExtractor._extract_via_javascript(page)
            if sitekey:
                logger.info(f"✅ Sitekey found via JavaScript: {sitekey}")
                return sitekey
            
            # Method 3: Page source analysis
            sitekey = await EnhancedSitekeyExtractor._extract_from_page_source(page)
            if sitekey:
                logger.info(f"✅ Sitekey found in page source: {sitekey}")
                return sitekey
            
            # Method 4: Network requests analysis
            sitekey = await EnhancedSitekeyExtractor._extract_from_network(page)
            if sitekey:
                logger.info(f"✅ Sitekey found in network requests: {sitekey}")
                return sitekey
            
            # Method 5: Deep iframe analysis for embedded challenges
            sitekey = await EnhancedSitekeyExtractor._extract_from_iframes(page)
            if sitekey:
                logger.info(f"✅ Sitekey found in iframe: {sitekey}")
                return sitekey
            
            # Method 6: Check for dynamically loaded content
            sitekey = await EnhancedSitekeyExtractor._extract_from_dynamic_content(page)
            if sitekey:
                logger.info(f"✅ Sitekey found in dynamic content: {sitekey}")
                return sitekey
            
            logger.warning("⚠️ No sitekey found with any method - challenge may not be solvable")
            return None
            
        except Exception as e:
            logger.error(f"❌ Sitekey extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_from_elements(page) -> Optional[str]:
        """Extract sitekey from page elements"""
        try:
            # Common sitekey attributes
            sitekey_selectors = [
                '[data-sitekey]',
                '[data-cf-turnstile-sitekey]',
                '[data-turnstile-sitekey]',
                '[data-captcha-sitekey]',
                '[data-site-key]',
                '.cf-turnstile[data-sitekey]',
                'iframe[src*="challenges.cloudflare.com"]',
                'script[src*="challenges.cloudflare.com"]'
            ]
            
            for selector in sitekey_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        # Try different attribute names
                        for attr in ['data-sitekey', 'data-cf-turnstile-sitekey', 'data-turnstile-sitekey', 'data-captcha-sitekey', 'data-site-key', 'sitekey']:
                            sitekey = await element.get_attribute(attr)
                            if sitekey and len(sitekey) > 10:
                                return sitekey
                        
                        # Check src attribute for iframes/scripts
                        src = await element.get_attribute('src')
                        if src and 'sitekey=' in src:
                            # Extract sitekey from URL
                            import re
                            match = re.search(r'sitekey=([^&]+)', src)
                            if match:
                                return match.group(1)
                                
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Element extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_via_javascript(page) -> Optional[str]:
        """Extract sitekey using JavaScript execution"""
        try:
            # JavaScript to find sitekey in various ways
            sitekey = await page.evaluate("""
                () => {
                    // Method 1: Check all elements for sitekey attributes
                    const elements = document.querySelectorAll('*');
                    for (let element of elements) {
                        const attrs = ['data-sitekey', 'data-cf-turnstile-sitekey', 'data-turnstile-sitekey', 'data-captcha-sitekey', 'data-site-key', 'sitekey'];
                        for (let attr of attrs) {
                            const value = element.getAttribute(attr);
                            if (value && value.length > 10) {
                                return value;
                            }
                        }
                    }
                    
                    // Method 2: Check window object for Turnstile/Cloudflare variables
                    if (window.turnstile && window.turnstile.sitekey) {
                        return window.turnstile.sitekey;
                    }
                    
                    if (window.cf && window.cf.sitekey) {
                        return window.cf.sitekey;
                    }
                    
                    // Method 3: Check for Turnstile render calls in scripts
                    const scripts = document.querySelectorAll('script');
                    for (let script of scripts) {
                        const content = script.textContent || script.innerHTML;
                        if (content.includes('turnstile.render') || content.includes('cf-turnstile')) {
                            const sitekeyMatch = content.match(/sitekey['"\\s]*[:=]['"\\s]*([0-9a-zA-Z_-]+)/);
                            if (sitekeyMatch && sitekeyMatch[1] && sitekeyMatch[1].length > 10) {
                                return sitekeyMatch[1];
                            }
                        }
                    }
                    
                    // Method 4: Check meta tags
                    const metaTags = document.querySelectorAll('meta');
                    for (let meta of metaTags) {
                        if (meta.name && meta.name.toLowerCase().includes('sitekey')) {
                            return meta.content;
                        }
                    }
                    
                    return null;
                }
            """)
            
            return sitekey if sitekey and len(sitekey) > 10 else None
            
        except Exception as e:
            logger.debug(f"JavaScript extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_from_page_source(page) -> Optional[str]:
        """Extract sitekey from page source"""
        try:
            content = await page.content()
            
            # Common patterns for sitekey in HTML
            import re
            patterns = [
                r'data-sitekey["\s]*=["\s]*([0-9a-zA-Z_-]+)',
                r'data-cf-turnstile-sitekey["\s]*=["\s]*([0-9a-zA-Z_-]+)',
                r'data-turnstile-sitekey["\s]*=["\s]*([0-9a-zA-Z_-]+)',
                r'sitekey["\s]*:["\s]*["\']([0-9a-zA-Z_-]+)["\']',
                r'sitekey["\s]*=["\s]*["\']([0-9a-zA-Z_-]+)["\']',
                r'cf-turnstile.*?sitekey["\s]*=["\s]*["\']([0-9a-zA-Z_-]+)["\']',
                r'turnstile\.render.*?sitekey["\s]*:["\s]*["\']([0-9a-zA-Z_-]+)["\']'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    if len(match) > 10:  # Valid sitekeys are longer than 10 chars
                        return match
            
            return None
            
        except Exception as e:
            logger.debug(f"Page source extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_from_network(page) -> Optional[str]:
        """Extract sitekey from network requests"""
        try:
            # This would require setting up request interception
            # For now, return None as it's complex to implement
            return None
            
        except Exception as e:
            logger.debug(f"Network extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_from_iframes(page) -> Optional[str]:
        """Extract sitekey from iframes (Cloudflare challenges often use iframes)"""
        try:
            # Find all iframes
            iframes = await page.query_selector_all('iframe')
            
            for iframe in iframes:
                try:
                    # Check iframe src for sitekey
                    src = await iframe.get_attribute('src')
                    if src and ('challenges.cloudflare.com' in src or 'turnstile' in src):
                        # Extract sitekey from iframe URL
                        import re
                        match = re.search(r'sitekey=([^&]+)', src)
                        if match:
                            return match.group(1)
                    
                    # Check iframe attributes
                    for attr in ['data-sitekey', 'data-cf-turnstile-sitekey', 'sitekey']:
                        sitekey = await iframe.get_attribute(attr)
                        if sitekey and len(sitekey) > 10:
                            return sitekey
                            
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Iframe extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_from_dynamic_content(page) -> Optional[str]:
        """Extract sitekey from dynamically loaded content"""
        try:
            # Wait for potential dynamic content to load
            await asyncio.sleep(2)
            
            # Re-run JavaScript extraction after waiting
            sitekey = await page.evaluate("""
                () => {
                    // Look for recently added elements
                    const recentElements = document.querySelectorAll('[data-sitekey], [data-cf-turnstile-sitekey], .cf-turnstile');
                    for (let element of recentElements) {
                        const attrs = ['data-sitekey', 'data-cf-turnstile-sitekey', 'data-turnstile-sitekey'];
                        for (let attr of attrs) {
                            const value = element.getAttribute(attr);
                            if (value && value.length > 10) {
                                return value;
                            }
                        }
                    }
                    
                    // Check for Turnstile widget initialization
                    if (window.turnstile && window.turnstile._widgets) {
                        for (let widget of Object.values(window.turnstile._widgets)) {
                            if (widget.sitekey) {
                                return widget.sitekey;
                            }
                        }
                    }
                    
                    return null;
                }
            """)
            
            return sitekey if sitekey and len(sitekey) > 10 else None
            
        except Exception as e:
            logger.debug(f"Dynamic content extraction error: {e}")
            return None
    
    @staticmethod
    async def _extract_from_cloudflare_challenge(page) -> Optional[str]:
        """Extract sitekey from Cloudflare challenge pages specifically"""
        try:
            current_url = page.url
            
            # Check if this is a Cloudflare challenge page
            if 'challenges.cloudflare.com' not in current_url and 'epicgames.com' not in current_url:
                return None
            
            # Check for Cloudflare challenge indicators
            page_title = await page.title()
            if 'Just a moment' not in page_title and 'challenges.cloudflare.com' not in current_url:
                return None
            
            logger.info("🔍 Detected Cloudflare challenge page, extracting sitekey...")
            
            # Method 1: Extract from URL parameters
            import re
            from urllib.parse import urlparse, parse_qs
            
            parsed_url = urlparse(current_url)
            query_params = parse_qs(parsed_url.query)
            
            # Look for sitekey in URL parameters
            for param_name in ['sitekey', 'k', 'site-key']:
                if param_name in query_params:
                    sitekey = query_params[param_name][0]
                    if sitekey and len(sitekey) > 10:
                        logger.info(f"✅ Found sitekey in URL parameter '{param_name}': {sitekey}")
                        return sitekey
            
            # Method 2: Extract from URL path or fragment
            url_match = re.search(r'[?&](?:sitekey|k|site-key)=([^&]+)', current_url)
            if url_match:
                sitekey = url_match.group(1)
                if sitekey and len(sitekey) > 10:
                    logger.info(f"✅ Found sitekey in URL: {sitekey}")
                    return sitekey
            
            # Method 3: Extract from page content (Cloudflare challenge pages often embed sitekey)
            page_content = await page.content()
            
            # Look for sitekey patterns in the HTML
            sitekey_patterns = [
                r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'data-sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'cf-turnstile-sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                r'"sitekey"\s*:\s*"([^"]+)"',
                r'\'sitekey\'\s*:\s*\'([^\']+)\'',
                r'sitekey=([^&\s"\']+)',
            ]
            
            for pattern in sitekey_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 10 and match.startswith('0x'):
                        logger.info(f"✅ Found sitekey in page content: {match}")
                        return match
            
            # Method 3.5: Look for sitekey-like patterns in the page content
            # Some Cloudflare challenges embed sitekeys in different ways
            sitekey_like_patterns = [
                r'0x[A-Za-z0-9_-]{20,}',  # Generic sitekey pattern
                r'0x[A-Za-z0-9_]{30,}',   # Longer sitekey pattern
            ]
            
            for pattern in sitekey_like_patterns:
                matches = re.findall(pattern, page_content)
                for match in matches:
                    # Filter out obvious non-sitekeys (like SVG paths, etc.)
                    if (len(match) >= 20 and len(match) <= 100 and 
                        not any(x in match.lower() for x in ['svg', 'path', 'font', 'css', 'style']) and
                        match.count('_') < 10 and match.count('-') < 10):
                        logger.info(f"✅ Found potential sitekey pattern in page content: {match}")
                        return match
            
            # Method 4: JavaScript extraction for Cloudflare challenges
            sitekey = await page.evaluate("""
                () => {
                    // Look for Cloudflare Turnstile widget
                    const turnstileElements = document.querySelectorAll('[data-sitekey], .cf-turnstile, #cf-turnstile, iframe[src*="challenges.cloudflare.com"]');
                    for (let element of turnstileElements) {
                        const sitekey = element.getAttribute('data-sitekey') || 
                                       element.getAttribute('data-cf-turnstile-sitekey') ||
                                       element.getAttribute('sitekey');
                        if (sitekey && sitekey.length > 10) {
                            return sitekey;
                        }
                        
                        // Check iframe src for sitekey
                        const src = element.getAttribute('src');
                        if (src && src.includes('challenges.cloudflare.com')) {
                            const match = src.match(/[?&]sitekey=([^&]+)/);
                            if (match && match[1] && match[1].length > 10) {
                                return match[1];
                            }
                        }
                    }
                    
                    // Check window object for Cloudflare data
                    if (window._cf_chl_opt && window._cf_chl_opt.cRay) {
                        // This is a Cloudflare challenge page, look for sitekey in various places
                        const chlOpt = window._cf_chl_opt;
                        if (chlOpt.sitekey) return chlOpt.sitekey;
                        if (chlOpt.cSitekey) return chlOpt.cSitekey;
                        if (chlOpt.turnstileSitekey) return chlOpt.turnstileSitekey;
                    }
                    
                    if (window.cf && window.cf.sitekey) {
                        return window.cf.sitekey;
                    }
                    
                    // Check for Turnstile configuration
                    if (window.turnstile && window.turnstile.sitekey) {
                        return window.turnstile.sitekey;
                    }
                    
                    // Look in all script tags for sitekey
                    const scripts = document.querySelectorAll('script');
                    for (let script of scripts) {
                        const content = script.textContent || script.innerHTML;
                        
                        // Multiple sitekey patterns
                        const patterns = [
                            /sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']/,
                            /"sitekey"\s*:\s*"([^"]+)"/,
                            /'sitekey'\s*:\s*'([^']+)'/,
                            /data-sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']/,
                            /turnstile.*sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']/,
                            /cf.*sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']/
                        ];
                        
                        for (let pattern of patterns) {
                            const match = content.match(pattern);
                            if (match && match[1] && match[1].length > 10 && match[1].startsWith('0x')) {
                                return match[1];
                            }
                        }
                    }
                    
                    return null;
                }
            """)
            
            if sitekey and len(sitekey) > 10:
                logger.info(f"✅ Found sitekey via JavaScript on Cloudflare challenge: {sitekey}")
                return sitekey
            
            logger.warning("⚠️ Could not extract sitekey from Cloudflare challenge page")
            return None
            
        except Exception as e:
            logger.debug(f"Cloudflare challenge extraction error: {e}")
            return None