API Reference
=============

This section provides detailed API reference documentation for all classes and functions in the Exo Mass Checker project.

Core Application API
--------------------

Main Application
~~~~~~~~~~~~~~~~

.. automodule:: main
   :members:
   :undoc-members:
   :show-inheritance:

Configuration API
-----------------

Settings
~~~~~~~~

.. automodule:: config.settings
   :members:
   :undoc-members:
   :show-inheritance:

Bot Interface API
-----------------

Keyboards
~~~~~~~~~

.. autoclass:: bot.keyboards.Keyboards
   :members:
   :undoc-members:
   :show-inheritance:

User Data Management
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: bot.user_data.UserData
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: bot.user_data.UserDataManager
   :members:
   :undoc-members:
   :show-inheritance:

Handlers API
------------

Start Handler
~~~~~~~~~~~~~

.. autofunction:: handlers.start_handler.start_command
.. autofunction:: handlers.start_handler.help_command
.. autofunction:: handlers.start_handler.status_command

File Handler
~~~~~~~~~~~~

.. autoclass:: handlers.file_handler.FileHandler
   :members:
   :undoc-members:
   :show-inheritance:

Callback Handler
~~~~~~~~~~~~~~~~

.. autoclass:: handlers.callback_handler.CallbackHandler
   :members:
   :undoc-members:
   :show-inheritance:

Utilities API
-------------

Account Checker
~~~~~~~~~~~~~~~

.. autoclass:: utils.account_checker.AccountChecker
   :members:
   :undoc-members:
   :show-inheritance:

Browser Manager
~~~~~~~~~~~~~~~

.. autoclass:: utils.browser_manager.BrowserManager
   :members:
   :undoc-members:
   :show-inheritance:

Authentication Handler
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: utils.auth_handler.AuthHandler
   :members:
   :undoc-members:
   :show-inheritance:

Login Handler
~~~~~~~~~~~~~

.. autoclass:: utils.login_handler.LoginHandler
   :members:
   :undoc-members:
   :show-inheritance:

File Manager
~~~~~~~~~~~~

.. autoclass:: utils.file_manager.FileManager
   :members:
   :undoc-members:
   :show-inheritance:

Solver Manager
~~~~~~~~~~~~~~

.. autoclass:: utils.solver_manager.SolverManager
   :members:
   :undoc-members:
   :show-inheritance:

Unified Turnstile Handler
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: utils.unified_turnstile_handler.UnifiedTurnstileHandler
   :members:
   :undoc-members:
   :show-inheritance:

Resource Monitor
~~~~~~~~~~~~~~~~

.. autoclass:: utils.resource_monitor.ResourceMonitor
   :members:
   :undoc-members:
   :show-inheritance:

Dropbox Uploader
~~~~~~~~~~~~~~~~

.. autoclass:: utils.dropbox_uploader.DropboxUploader
   :members:
   :undoc-members:
   :show-inheritance:

Epic API Client
~~~~~~~~~~~~~~~

.. autoclass:: utils.epic_api_client.EpicAPIClient
   :members:
   :undoc-members:
   :show-inheritance:

Display Detector
~~~~~~~~~~~~~~~~

.. autoclass:: utils.display_detector.DisplayDetector
   :members:
   :undoc-members:
   :show-inheritance:

User Agent Manager
~~~~~~~~~~~~~~~~~~

.. autoclass:: utils.user_agent_manager.UserAgentManager
   :members:
   :undoc-members:
   :show-inheritance:

Solvers API
-----------

Turnstile Solver API
~~~~~~~~~~~~~~~~~~~~

.. automodule:: solvers.turnstile_solver.api_solver
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: solvers.turnstile_solver.async_solver.AsyncTurnstileSolver
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: solvers.turnstile_solver.sync_solver.SyncTurnstileSolver
   :members:
   :undoc-members:
   :show-inheritance:

Cloudflare Bypass API
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: solvers.cloudflare_bypass.CloudflareBypasser.CloudflareBypasser
   :members:
   :undoc-members:
   :show-inheritance:

BotForge Solver API
~~~~~~~~~~~~~~~~~~~

.. autoclass:: solvers.cloudflare_botsforge.browser.BotForgeBrowser
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: solvers.cloudflare_botsforge.app.BotForgeApp
   :members:
   :undoc-members:
   :show-inheritance: