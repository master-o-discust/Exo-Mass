"""
CloudFlare Bypass - DrissionPage implementation
Based on sarperavci/CloudflareBypassForScraping repository
"""

try:
    from .CloudflareBypasser import CloudflareBypasser
    DRISSION_AVAILABLE = True
except ImportError as e:
    DRISSION_AVAILABLE = False
    CloudflareBypasser = None

__all__ = ['CloudflareBypasser', 'DRISSION_AVAILABLE']