"""
Solver Manager - Centralized initialization and management of all solvers
Ensures all solvers are properly initialized when the server starts
"""
import asyncio
import logging
import sys
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SolverStatus:
    """Status of a solver"""
    name: str
    available: bool
    initialized: bool
    error: Optional[str] = None
    version: Optional[str] = None

class SolverManager:
    """Centralized manager for all Turnstile/Cloudflare solvers"""
    
    def __init__(self):
        self.solvers = {}
        self.solver_status = {}
        self.initialized = False
        
    async def initialize_all_solvers(self) -> Dict[str, SolverStatus]:
        """Initialize all available solvers and return their status"""
        logger.info("🚀 Initializing all Turnstile/Cloudflare solvers...")
        
        # Initialize each solver
        await self._initialize_turnstile_solver()
        await self._initialize_botsforge_solver()
        await self._initialize_drission_bypasser()
        
        self.initialized = True
        
        # Log summary
        available_count = sum(1 for status in self.solver_status.values() if status.available)
        total_count = len(self.solver_status)
        
        logger.info(f"✅ Solver initialization complete: {available_count}/{total_count} solvers available")
        
        for name, status in self.solver_status.items():
            if status.available:
                logger.info(f"   ✅ {name}: Ready")
            else:
                logger.warning(f"   ❌ {name}: {status.error}")
        
        return self.solver_status
    
    async def _initialize_turnstile_solver(self):
        """Initialize the primary Turnstile solver"""
        try:
            # Add turnstile_solver to path if needed
            turnstile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'solvers', 'turnstile_solver')
            if turnstile_path not in sys.path:
                sys.path.insert(0, turnstile_path)
            
            from solvers.turnstile_solver import AsyncTurnstileSolver, TurnstileResult, ASYNC_SOLVER_AVAILABLE
            
            # Check if the async solver is actually available
            if not ASYNC_SOLVER_AVAILABLE or AsyncTurnstileSolver is None:
                raise ImportError("AsyncTurnstileSolver is not available - likely missing dependencies")
            
            # Test basic initialization (don't actually create browser yet)
            # Just verify the class can be instantiated
            try:
                # This is a lightweight test - just check if we can create the class
                test_solver = AsyncTurnstileSolver.__new__(AsyncTurnstileSolver)
                if test_solver is None:
                    raise Exception("Failed to create AsyncTurnstileSolver instance")
            except Exception as e:
                raise Exception(f"AsyncTurnstileSolver instantiation failed: {e}")
            
            # Store solver class for later use
            self.solvers['turnstile_solver'] = {
                'class': AsyncTurnstileSolver,
                'result_class': TurnstileResult,
                'initialized': True
            }
            
            self.solver_status['turnstile_solver'] = SolverStatus(
                name="Turnstile Solver (Primary)",
                available=True,
                initialized=True,
                version="1.0"
            )
            
            logger.info("✅ Turnstile Solver initialized successfully")
            
        except ImportError as e:
            error_msg = f"Import failed: {e}"
            self.solver_status['turnstile_solver'] = SolverStatus(
                name="Turnstile Solver (Primary)",
                available=False,
                initialized=False,
                error=error_msg
            )
            logger.warning(f"⚠️ Turnstile Solver not available: {error_msg}")
            
        except Exception as e:
            error_msg = f"Initialization failed: {e}"
            self.solver_status['turnstile_solver'] = SolverStatus(
                name="Turnstile Solver (Primary)",
                available=False,
                initialized=False,
                error=error_msg
            )
            logger.error(f"❌ Turnstile Solver initialization error: {error_msg}")
    
    async def _initialize_botsforge_solver(self):
        """Initialize the BotsForge CloudFlare solver"""
        try:
            from solvers.cloudflare_botsforge.browser import Browser as CloudflareBrowser
            from solvers.cloudflare_botsforge.models import CaptchaTask
            
            # Test initialization
            test_browser = CloudflareBrowser()
            
            # Store solver components for later use
            self.solvers['botsforge'] = {
                'browser_class': CloudflareBrowser,
                'task_class': CaptchaTask,
                'initialized': True
            }
            
            self.solver_status['botsforge'] = SolverStatus(
                name="BotsForge CloudFlare (Fallback 1)",
                available=True,
                initialized=True,
                version="1.0"
            )
            
            logger.info("✅ BotsForge CloudFlare solver initialized successfully")
            
        except ImportError as e:
            error_msg = f"Import failed: {e}"
            self.solver_status['botsforge'] = SolverStatus(
                name="BotsForge CloudFlare (Fallback 1)",
                available=False,
                initialized=False,
                error=error_msg
            )
            logger.warning(f"⚠️ BotsForge solver not available: {error_msg}")
            
        except Exception as e:
            error_msg = f"Initialization failed: {e}"
            self.solver_status['botsforge'] = SolverStatus(
                name="BotsForge CloudFlare (Fallback 1)",
                available=False,
                initialized=False,
                error=error_msg
            )
            logger.error(f"❌ BotsForge solver initialization error: {error_msg}")
    
    async def _initialize_drission_bypasser(self):
        """Initialize the Patchright + Camoufox CloudFlare bypasser (replacing DrissionPage)"""
        try:
            from patchright.async_api import async_playwright as patchright_async
            from camoufox.async_api import AsyncCamoufox
            
            # Test that both Patchright and Camoufox are available
            # Don't actually create instances, just test imports
            
            # Store solver components for later use
            self.solvers['drission_bypass'] = {
                'patchright_async': patchright_async,
                'camoufox_class': AsyncCamoufox,
                'initialized': True
            }
            
            self.solver_status['drission_bypass'] = SolverStatus(
                name="Patchright + Camoufox Bypasser (Fallback 2)",
                available=True,
                initialized=True,
                version="1.0"
            )
            
            logger.info("✅ Patchright + Camoufox CloudFlare bypasser initialized successfully")
            
        except ImportError as e:
            error_msg = f"Import failed: {e}"
            self.solver_status['drission_bypass'] = SolverStatus(
                name="Patchright + Camoufox Bypasser (Fallback 2)",
                available=False,
                initialized=False,
                error=error_msg
            )
            logger.warning(f"⚠️ Patchright + Camoufox bypasser not available: {error_msg}")
            
        except Exception as e:
            error_msg = f"Initialization failed: {e}"
            self.solver_status['drission_bypass'] = SolverStatus(
                name="Patchright + Camoufox Bypasser (Fallback 2)",
                available=False,
                initialized=False,
                error=error_msg
            )
            logger.error(f"❌ Patchright + Camoufox bypasser initialization error: {error_msg}")
    
    def get_solver_status(self) -> Dict[str, SolverStatus]:
        """Get the status of all solvers"""
        return self.solver_status.copy()
    
    def is_solver_available(self, solver_name: str) -> bool:
        """Check if a specific solver is available"""
        status = self.solver_status.get(solver_name)
        return status is not None and status.available
    
    def get_available_solvers(self) -> List[str]:
        """Get list of available solver names"""
        return [name for name, status in self.solver_status.items() if status.available]
    
    def get_solver_components(self, solver_name: str) -> Optional[Dict[str, Any]]:
        """Get the components for a specific solver"""
        if not self.is_solver_available(solver_name):
            return None
        return self.solvers.get(solver_name)
    
    async def start_turnstile_service(self):
        """Start the Turnstile API service if available"""
        if not self.is_solver_available('turnstile_solver'):
            logger.warning("⚠️ Cannot start Turnstile service - solver not available")
            return False
        
        try:
            from config.settings import (
                TURNSTILE_SERVICE_HOST, 
                TURNSTILE_SERVICE_PORT, 
                TURNSTILE_SERVICE_THREADS,
                ENABLE_TURNSTILE_SERVICE
            )
            
            if not ENABLE_TURNSTILE_SERVICE:
                logger.info("ℹ️ Turnstile service disabled in config")
                return False
            
            # Add turnstile_solver to path
            turnstile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'solvers', 'turnstile_solver')
            if turnstile_path not in sys.path:
                sys.path.insert(0, turnstile_path)
            
            from api_solver import create_app
            import hypercorn.asyncio
            
            logger.info(f"🚀 Starting Turnstile API service")
            logger.info(f"   Host: {TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}")
            logger.info(f"   Threads: {TURNSTILE_SERVICE_THREADS}")
            
            # Create the Turnstile solver app
            app = create_app(
                headless=True,  # Always headless for server
                useragent=None,  # Let the service choose
                debug=False,  # Disable debug for production
                browser_type="camoufox",  # Force Camoufox for enhanced stealth
                thread=TURNSTILE_SERVICE_THREADS,
                proxy_support=True  # Enable proxy support
            )
            
            # Configure hypercorn
            config = hypercorn.Config()
            config.bind = [f"{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}"]
            config.use_reloader = False
            config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s"
            
            # Start the service in background
            asyncio.create_task(hypercorn.asyncio.serve(app, config))
            
            logger.info("✅ Turnstile API service started successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Turnstile service: {e}")
            return False

    async def start_botsforge_service(self):
        """Start the BotsForge API service if available"""
        if not self.is_solver_available("botsforge"):
            logger.warning("⚠️ Cannot start BotsForge service - solver not available")
            return False

        try:
            logger.info(f"🚀 Starting BotsForge API service")
            logger.info(f"   Host: 127.0.0.1:5033")

            # Set environment variables for BotsForge
            root_dir = os.path.dirname(os.path.dirname(__file__))
            botsforge_dir = os.path.join(root_dir, "solvers", "cloudflare_botsforge")
            
            # Import and start BotsForge server
            import asyncio

            # Start BotsForge server as subprocess using the fixed launcher
            launcher_path = os.path.join(root_dir, "launch_botsforge.py")
            cmd = [sys.executable, launcher_path]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = root_dir
            env["PORT"] = "5033"
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                cwd=root_dir,  # Run from root directory since launcher is there
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Give it a moment to start
            await asyncio.sleep(3)
            
            if process.returncode is None:  # Still running
                logger.info("✅ BotsForge API service started successfully!")
                return True
            else:
                stdout, stderr = await process.communicate()
                logger.error(f"❌ BotsForge service failed to start (exit code: {process.returncode})")
                if stderr:
                    logger.error(f"   Error: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to start BotsForge service: {e}")
            return False


# Global solver manager instance
solver_manager = SolverManager()

async def initialize_solvers() -> Dict[str, SolverStatus]:
    """Initialize all solvers - call this at startup"""
    return await solver_manager.initialize_all_solvers()

def get_solver_manager() -> SolverManager:
    """Get the global solver manager instance"""
    return solver_manager