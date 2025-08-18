#!/usr/bin/env python3
"""
Test CloudFlare Challenge Routing
Tests that CloudFlare challenges are properly routed to solver servers
"""
import asyncio
import sys
import os
from loguru import logger

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.unified_turnstile_handler import UnifiedTurnstileHandler

async def test_cloudflare_routing():
    """Test CloudFlare challenge routing to solver servers"""
    logger.info("🧪 Testing CloudFlare Challenge Routing")
    logger.info("=" * 50)
    
    # Create handler
    handler = UnifiedTurnstileHandler()
    
    # Test challenge info structure
    test_challenge = {
        "detected": True,
        "url": "https://example.com",
        "sitekey": "0x4AAAAAAADnPIDROzLVaoAo",
        "method": "turnstile_solver"
    }
    
    logger.info("📍 Testing Turnstile Solver routing...")
    try:
        result = await handler.solve_with_turnstile_solver(test_challenge)
        if result.get("success"):
            logger.info("✅ Turnstile Solver: Successfully routed and processed")
        else:
            logger.info(f"⚠️ Turnstile Solver: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"❌ Turnstile Solver routing error: {e}")
    
    logger.info("📍 Testing BotsForge routing...")
    try:
        result = await handler.solve_with_botsforge(test_challenge)
        if result.get("success"):
            logger.info("✅ BotsForge: Successfully routed and processed")
        else:
            logger.info(f"⚠️ BotsForge: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"❌ BotsForge routing error: {e}")
    
    logger.info("📍 Testing DrissionPage bypasser routing...")
    try:
        result = await handler.solve_with_drission_bypass(test_challenge)
        if result.get("success"):
            logger.info("✅ DrissionPage: Successfully routed and processed")
        else:
            logger.info(f"⚠️ DrissionPage: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"❌ DrissionPage routing error: {e}")
    
    logger.info("=" * 50)
    logger.info("🎯 CloudFlare routing test completed!")

if __name__ == "__main__":
    asyncio.run(test_cloudflare_routing())