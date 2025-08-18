#!/usr/bin/env python3
"""
Test script to verify HTTP API integration for Turnstile solvers
"""

import asyncio
import aiohttp
import json
import time
from config.settings import (
    TURNSTILE_SERVICE_HOST, TURNSTILE_SERVICE_PORT,
    BOTSFORGE_SERVICE_HOST, BOTSFORGE_SERVICE_PORT
)

async def test_turnstile_api():
    """Test the Theyka/Turnstile-Solver HTTP API"""
    print("🧪 Testing Turnstile API...")
    
    try:
        # Test basic connectivity
        api_url = f"http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}/"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print(f"✅ Turnstile API is accessible at {api_url}")
                    return True
                else:
                    print(f"❌ Turnstile API returned status {response.status}")
                    return False
                    
    except aiohttp.ClientConnectorError:
        print(f"❌ Cannot connect to Turnstile API at {api_url}")
        print("   Make sure the Turnstile service is running on the specified host/port")
        return False
    except Exception as e:
        print(f"❌ Error testing Turnstile API: {e}")
        return False

async def test_botsforge_api():
    """Test the BotsForge/CloudFlare HTTP API"""
    print("🧪 Testing BotsForge API...")
    
    try:
        # Test basic connectivity with a simple createTask request
        api_url = f"http://{BOTSFORGE_SERVICE_HOST}:{BOTSFORGE_SERVICE_PORT}/createTask"
        
        # Get the correct API key
        from config.settings import BOTSFORGE_API_KEY
        
        # Simple test payload (will likely fail but should return proper error)
        test_payload = {
            "clientKey": BOTSFORGE_API_KEY or "test-key",
            "task": {
                "type": "AntiTurnstileTaskProxyLess",
                "websiteURL": "https://example.com",
                "websiteKey": "0x4AAAAAAADnPIDROzLVaoAo"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url, 
                json=test_payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ BotsForge API is accessible at {api_url}")
                    print(f"   Response: {result}")
                    return True
                else:
                    print(f"❌ BotsForge API returned status {response.status}")
                    error_text = await response.text()
                    print(f"   Error: {error_text}")
                    return False
                    
    except aiohttp.ClientConnectorError:
        print(f"❌ Cannot connect to BotsForge API at {api_url}")
        print("   Make sure the BotsForge service is running on the specified host/port")
        return False
    except Exception as e:
        print(f"❌ Error testing BotsForge API: {e}")
        return False

async def main():
    """Run all API tests"""
    print("🚀 Testing HTTP API Integration for Turnstile Solvers")
    print("=" * 60)
    
    print(f"📍 Configuration:")
    print(f"   Turnstile API: http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}")
    print(f"   BotsForge API: http://{BOTSFORGE_SERVICE_HOST}:{BOTSFORGE_SERVICE_PORT}")
    print()
    
    # Test APIs
    turnstile_ok = await test_turnstile_api()
    print()
    botsforge_ok = await test_botsforge_api()
    print()
    
    # Summary
    print("=" * 60)
    print("📊 Test Results:")
    print(f"   Turnstile API: {'✅ OK' if turnstile_ok else '❌ FAILED'}")
    print(f"   BotsForge API: {'✅ OK' if botsforge_ok else '❌ FAILED'}")
    
    if turnstile_ok and botsforge_ok:
        print("\n🎉 All HTTP APIs are accessible and ready!")
    else:
        print("\n⚠️  Some APIs are not accessible. Please check the services are running.")
        print("\nTo start the services:")
        if not turnstile_ok:
            print("   Turnstile: Run the Theyka/Turnstile-Solver server")
        if not botsforge_ok:
            print("   BotsForge: Run the BotsForge/CloudFlare server")

if __name__ == "__main__":
    asyncio.run(main())