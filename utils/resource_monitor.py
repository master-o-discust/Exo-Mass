"""
Resource monitoring utility for the Mass-checker application
Provides centralized resource monitoring and alerting capabilities
"""
import logging
import psutil
import time
import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from config.settings import ENABLE_RESOURCE_MONITORING, DEBUG_ENHANCED_FEATURES

logger = logging.getLogger(__name__)


@dataclass
class ResourceAlert:
    """Resource alert information"""
    alert_type: str
    message: str
    current_value: float
    threshold: float
    timestamp: float


class ResourceMonitor:
    """Centralized resource monitoring for the application"""
    
    def __init__(self):
        self.process = psutil.Process() if ENABLE_RESOURCE_MONITORING else None
        self.initial_memory = (self.process.memory_info().rss / 1024 / 1024 
                              if self.process else 0)  # MB
        self.start_time = time.time()
        self.alerts: list[ResourceAlert] = []
        self.alert_callbacks: list[Callable] = []
        
        # Thresholds
        self.memory_warning_mb = 512
        self.memory_critical_mb = 1024
        self.cpu_warning_percent = 80
        self.cpu_critical_percent = 95
        
        # Monitoring state
        self.last_check_time = 0
        self.check_interval = 30  # Check every 30 seconds
        self.monitoring_active = False
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        try:
            if not self.process:
                return {'monitoring_enabled': False}
            
            # Process information
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent()
            
            # System information
            system_memory = psutil.virtual_memory()
            system_cpu = psutil.cpu_percent(interval=1)
            
            uptime = time.time() - self.start_time
            
            return {
                'monitoring_enabled': True,
                'process': {
                    'memory_mb': memory_info.rss / 1024 / 1024,
                    'memory_growth_mb': (memory_info.rss / 1024 / 1024) - self.initial_memory,
                    'cpu_percent': cpu_percent,
                    'uptime_seconds': uptime
                },
                'system': {
                    'memory_total_mb': system_memory.total / 1024 / 1024,
                    'memory_available_mb': system_memory.available / 1024 / 1024,
                    'memory_percent': system_memory.percent,
                    'cpu_percent': system_cpu,
                    'cpu_count': psutil.cpu_count()
                },
                'timestamp': time.time()
            }
        except Exception as e:
            logger.warning(f"⚠️ Error getting system info: {e}")
            return {'monitoring_enabled': False, 'error': str(e)}
    
    def check_thresholds(self, info: Dict[str, Any]) -> list[ResourceAlert]:
        """Check if any resource thresholds are exceeded"""
        alerts = []
        
        if not info.get('monitoring_enabled'):
            return alerts
        
        try:
            process_info = info.get('process', {})
            system_info = info.get('system', {})
            timestamp = info.get('timestamp', time.time())
            
            # Check process memory
            memory_mb = process_info.get('memory_mb', 0)
            if memory_mb > self.memory_critical_mb:
                alerts.append(ResourceAlert(
                    alert_type='memory_critical',
                    message=f'Process memory usage critical: {memory_mb:.1f}MB',
                    current_value=memory_mb,
                    threshold=self.memory_critical_mb,
                    timestamp=timestamp
                ))
            elif memory_mb > self.memory_warning_mb:
                alerts.append(ResourceAlert(
                    alert_type='memory_warning',
                    message=f'Process memory usage high: {memory_mb:.1f}MB',
                    current_value=memory_mb,
                    threshold=self.memory_warning_mb,
                    timestamp=timestamp
                ))
            
            # Check process CPU
            cpu_percent = process_info.get('cpu_percent', 0)
            if cpu_percent > self.cpu_critical_percent:
                alerts.append(ResourceAlert(
                    alert_type='cpu_critical',
                    message=f'Process CPU usage critical: {cpu_percent:.1f}%',
                    current_value=cpu_percent,
                    threshold=self.cpu_critical_percent,
                    timestamp=timestamp
                ))
            elif cpu_percent > self.cpu_warning_percent:
                alerts.append(ResourceAlert(
                    alert_type='cpu_warning',
                    message=f'Process CPU usage high: {cpu_percent:.1f}%',
                    current_value=cpu_percent,
                    threshold=self.cpu_warning_percent,
                    timestamp=timestamp
                ))
            
            # Check system memory
            system_memory_percent = system_info.get('memory_percent', 0)
            if system_memory_percent > 90:
                alerts.append(ResourceAlert(
                    alert_type='system_memory_critical',
                    message=f'System memory usage critical: {system_memory_percent:.1f}%',
                    current_value=system_memory_percent,
                    threshold=90,
                    timestamp=timestamp
                ))
            elif system_memory_percent > 80:
                alerts.append(ResourceAlert(
                    alert_type='system_memory_warning',
                    message=f'System memory usage high: {system_memory_percent:.1f}%',
                    current_value=system_memory_percent,
                    threshold=80,
                    timestamp=timestamp
                ))
            
        except Exception as e:
            logger.warning(f"⚠️ Error checking thresholds: {e}")
        
        return alerts
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """Add a callback to be called when alerts are triggered"""
        self.alert_callbacks.append(callback)
    
    async def trigger_alerts(self, alerts: list[ResourceAlert]):
        """Trigger all alert callbacks for the given alerts"""
        for alert in alerts:
            self.alerts.append(alert)
            
            # Log the alert
            if alert.alert_type.endswith('_critical'):
                logger.error(f"🚨 {alert.message}")
            else:
                logger.warning(f"⚠️ {alert.message}")
            
            # Call alert callbacks
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"❌ Error in alert callback: {e}")
    
    async def check_resources(self) -> Optional[Dict[str, Any]]:
        """Check resources and trigger alerts if necessary"""
        current_time = time.time()
        
        # Check if it's time for a resource check
        if current_time - self.last_check_time < self.check_interval:
            return None
        
        self.last_check_time = current_time
        
        # Get system information
        info = self.get_system_info()
        
        # Check thresholds and trigger alerts
        alerts = self.check_thresholds(info)
        if alerts:
            await self.trigger_alerts(alerts)
        
        # Log resource info if debugging is enabled
        if DEBUG_ENHANCED_FEATURES and info.get('monitoring_enabled'):
            process_info = info.get('process', {})
            logger.info(f"📊 Resource check: "
                       f"Memory: {process_info.get('memory_mb', 0):.1f}MB "
                       f"(+{process_info.get('memory_growth_mb', 0):.1f}MB), "
                       f"CPU: {process_info.get('cpu_percent', 0):.1f}%")
        
        return info
    
    def get_recent_alerts(self, minutes: int = 5) -> list[ResourceAlert]:
        """Get alerts from the last N minutes"""
        cutoff_time = time.time() - (minutes * 60)
        return [alert for alert in self.alerts if alert.timestamp > cutoff_time]
    
    def clear_old_alerts(self, hours: int = 1):
        """Clear alerts older than N hours"""
        cutoff_time = time.time() - (hours * 3600)
        self.alerts = [alert for alert in self.alerts if alert.timestamp > cutoff_time]
    
    async def start_monitoring(self):
        """Start continuous resource monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        logger.info("🔍 Starting resource monitoring")
        
        while self.monitoring_active:
            try:
                await self.check_resources()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Error in resource monitoring: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop continuous resource monitoring"""
        self.monitoring_active = False
        logger.info("🛑 Stopping resource monitoring")


# Global resource monitor instance
resource_monitor = ResourceMonitor()


async def get_resource_info() -> Dict[str, Any]:
    """Get current resource information"""
    return resource_monitor.get_system_info()


async def check_resources() -> Optional[Dict[str, Any]]:
    """Check resources and return info if check was performed"""
    return await resource_monitor.check_resources()


def add_resource_alert_callback(callback: Callable[[ResourceAlert], None]):
    """Add a callback for resource alerts"""
    resource_monitor.add_alert_callback(callback)