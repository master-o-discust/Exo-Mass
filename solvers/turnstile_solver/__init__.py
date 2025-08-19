"""
Turnstile Solver - Main solver implementation
Based on Theyka/Turnstile-Solver repository
"""

try:
    from .async_solver import AsyncTurnstileSolver, TurnstileResult
    ASYNC_SOLVER_AVAILABLE = True
except ImportError as e:
    ASYNC_SOLVER_AVAILABLE = False
    AsyncTurnstileSolver = None
    TurnstileResult = None

try:
    from .api_solver import app as api_app
    API_SERVER_AVAILABLE = True
except ImportError as e:
    API_SERVER_AVAILABLE = False
    api_app = None

__all__ = ['AsyncTurnstileSolver', 'TurnstileResult', 'api_app', 
           'ASYNC_SOLVER_AVAILABLE', 'API_SERVER_AVAILABLE']