# 📖 API Reference Guide
## Exo Mass Checker - Complete Function & Class Reference

**Generated:** December 2024  
**Coverage:** 42 Python files, 7,887 lines of code  
**Documentation Type:** Manual API Analysis  

---

## 📋 API Overview

This document provides comprehensive API reference for all public classes, functions, and methods in the Exo Mass Checker project. The API is organized by module and includes detailed parameter descriptions, return values, and usage examples.

---

## 🎯 Core Application API

### 📄 main.py

#### `async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
**Purpose:** Global error handler for Telegram bot operations

**Parameters:**
- `update` (Update): Telegram update object containing error information
- `context` (ContextTypes.DEFAULT_TYPE): Bot context with error details

**Functionality:**
- Logs all unhandled exceptions with full traceback
- Provides user-friendly error messages to Telegram users
- Implements error recovery mechanisms
- Tracks error patterns for debugging

**Usage Example:**
```python
application.add_error_handler(error_handler)
```

#### `async def setup_bot_commands(application: Application) -> None`
**Purpose:** Register all bot commands and handlers

**Parameters:**
- `application` (Application): Telegram bot application instance

**Registered Handlers:**
- Command handlers: `/start`, `/help`, `/status`
- Message handlers: Document uploads, text messages
- Callback query handlers: Interactive button responses
- Error handlers: Global error handling

#### `async def initialize_all_systems() -> None`
**Purpose:** Initialize all system components and services

**Initialization Sequence:**
1. Directory creation (temp, data)
2. Resource monitor startup
3. Solver manager initialization
4. Dropbox service setup
5. System health checks

#### `def main() -> None`
**Purpose:** Application entry point and main execution loop

**Execution Flow:**
1. Environment validation
2. System initialization scheduling
3. Bot application building
4. Handler registration
5. Polling startup with error handling

---

## ⚙️ Configuration API

### 📄 config/settings.py

#### Environment Variables
```python
# Bot Configuration
BOT_TOKEN: str                    # Telegram bot token (required)
ADMIN_USER_ID: int               # Admin user ID for privileged operations

# File Management
TEMP_DIR: str = 'temp'           # Temporary file storage directory
DATA_DIR: str = 'data'           # Persistent data storage directory
MAX_FILE_SIZE: int = 52428800    # Maximum upload file size (50MB)
SUPPORTED_FILE_TYPES: List[str]  # Supported file extensions ['.txt']

# Browser Configuration
USE_ENHANCED_BROWSER: bool = True         # Enable enhanced browser features
PREFERRED_BROWSER_TYPE: str = 'camoufox'  # Default browser type
HEADLESS: bool = True                     # Run browsers in headless mode
NAVIGATION_TIMEOUT: int = 30000           # Page navigation timeout (ms)

# Performance Settings
MAX_CONCURRENT_CHECKS: int = 2            # Maximum concurrent account checks
MAX_CONTEXTS_PER_BROWSER: int = 1         # Browser contexts per instance
MEMORY_THRESHOLD_MB: int = 1024           # Memory cleanup threshold

# Cloudflare Solver Settings
ENABLE_TURNSTILE_SERVICE: bool = True     # Enable Turnstile API service
TURNSTILE_SERVICE_HOST: str = '127.0.0.1' # Turnstile service host
TURNSTILE_SERVICE_PORT: int = 5000        # Turnstile service port
```

---

## 🤖 Bot Interface API

### 📄 bot/keyboards.py

#### `class Keyboards`
**Purpose:** Static inline keyboard definitions for Telegram bot

##### `@staticmethod def main_menu() -> InlineKeyboardMarkup`
**Returns:** Main menu keyboard with primary actions
**Buttons:**
- "📁 Upload Accounts" → `upload_accounts`
- "🌐 Upload Proxies" → `upload_proxies`
- "▶️ Start Checking" → `start_checking`
- "📊 Check Status" → `check_status`
- "❓ Help" → `help`

##### `@staticmethod def checking_menu() -> InlineKeyboardMarkup`
**Returns:** Checking progress menu
**Buttons:**
- "📈 View Progress" → `view_progress`
- "⏹️ Cancel Checking" → `cancel_checking`
- "🏠 Main Menu" → `main_menu`

##### `@staticmethod def results_menu() -> InlineKeyboardMarkup`
**Returns:** Results management menu
**Buttons:**
- "📥 Download All Results" → `download_all`
- "✅ Download Valid Only" → `download_valid`
- "❌ Download Invalid Only" → `download_invalid`
- "🔐 Download 2FA Required" → `download_2fa`
- "🤖 Download CAPTCHA Required" → `download_captcha`

### 📄 bot/user_data.py

#### `class UserData`
**Purpose:** Individual user session data management

##### `def __init__(self, user_id: int)`
**Parameters:**
- `user_id` (int): Telegram user ID

**Attributes:**
- `user_id`: Telegram user identifier
- `accounts_file`: Path to uploaded accounts file
- `proxies_file`: Path to uploaded proxies file
- `is_checking`: Current checking status
- `progress`: Checking progress information
- `results`: Account checking results
- `last_activity`: Last user activity timestamp

##### `def set_accounts_file(self, file_path: str) -> None`
**Purpose:** Set the accounts file path for the user
**Parameters:**
- `file_path` (str): Absolute path to accounts file

##### `def set_proxies_file(self, file_path: str) -> None`
**Purpose:** Set the proxies file path for the user
**Parameters:**
- `file_path` (str): Absolute path to proxies file

##### `def start_checking(self) -> None`
**Purpose:** Mark user as currently checking accounts
**Side Effects:**
- Sets `is_checking` to True
- Initializes progress tracking
- Records start timestamp

##### `def update_progress(self, checked: int, total: int) -> None`
**Purpose:** Update checking progress
**Parameters:**
- `checked` (int): Number of accounts processed
- `total` (int): Total number of accounts

##### `def set_results(self, results: List[Dict]) -> None`
**Purpose:** Store account checking results
**Parameters:**
- `results` (List[Dict]): List of account result dictionaries

#### `class UserDataManager`
**Purpose:** Global user data management singleton

##### `def get_user_data(self, user_id: int) -> UserData`
**Purpose:** Get or create user data instance
**Parameters:**
- `user_id` (int): Telegram user ID
**Returns:** UserData instance for the user

##### `def cleanup_inactive_users(self, max_age_hours: int = 24) -> None`
**Purpose:** Remove inactive user data to free memory
**Parameters:**
- `max_age_hours` (int): Maximum age for user data retention

---

## 📨 Handlers API

### 📄 handlers/start_handler.py

#### `async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
**Purpose:** Handle /start command
**Parameters:**
- `update` (Update): Telegram update object
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Functionality:**
- Welcome message display
- User registration/initialization
- Main menu keyboard presentation
- Usage instructions

#### `async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
**Purpose:** Handle /help command
**Parameters:**
- `update` (Update): Telegram update object
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Help Content:**
- Bot feature overview
- File format requirements
- Usage instructions
- Troubleshooting tips

#### `async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
**Purpose:** Handle /status command (admin only)
**Parameters:**
- `update` (Update): Telegram update object
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Status Information:**
- System resource usage
- Active user count
- Checking queue status
- Performance metrics

### 📄 handlers/file_handler.py

#### `class FileHandler`
**Purpose:** Handle file uploads and processing

##### `@staticmethod async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
**Purpose:** Process uploaded documents
**Parameters:**
- `update` (Update): Telegram update with document
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Validation Checks:**
- File size validation (max 50MB)
- File type validation (.txt only)
- Content format validation
- Duplicate upload prevention

**Processing Steps:**
1. File download and validation
2. Content parsing and verification
3. User data storage
4. Confirmation message with statistics

##### `@staticmethod async def _validate_file(document) -> Tuple[bool, str]`
**Purpose:** Validate uploaded file
**Parameters:**
- `document`: Telegram document object
**Returns:** Tuple of (is_valid, error_message)

**Validation Rules:**
- File size ≤ 50MB
- File extension in ['.txt']
- Non-empty file content
- Valid encoding (UTF-8)

##### `@staticmethod async def _parse_accounts_file(file_path: str) -> Tuple[List[str], Dict[str, int]]`
**Purpose:** Parse accounts file content
**Parameters:**
- `file_path` (str): Path to accounts file
**Returns:** Tuple of (valid_accounts, statistics)

**Expected Format:**
```
email1@example.com:password1
email2@example.com:password2
```

**Statistics:**
- Total lines processed
- Valid accounts found
- Invalid format lines
- Duplicate accounts removed

### 📄 handlers/callback_handler.py

#### `class CallbackHandler`
**Purpose:** Handle Telegram callback queries from inline keyboards

##### `@staticmethod async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
**Purpose:** Route callback queries to appropriate handlers
**Parameters:**
- `update` (Update): Telegram update with callback query
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Supported Callbacks:**
- `main_menu`: Show main menu
- `upload_accounts`: Request accounts file upload
- `upload_proxies`: Request proxies file upload
- `start_checking`: Begin account verification
- `check_status`: Show checking progress
- `cancel_checking`: Cancel ongoing checks
- `download_*`: Download result files

##### `@staticmethod async def _start_checking(query, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None`
**Purpose:** Initialize account checking process
**Parameters:**
- `query`: Telegram callback query
- `context` (ContextTypes.DEFAULT_TYPE): Bot context
- `user_id` (int): User identifier

**Prerequisites:**
- Accounts file uploaded
- User not currently checking
- System resources available

**Process:**
1. Validate prerequisites
2. Initialize AccountChecker
3. Start background checking task
4. Update user interface

##### `@staticmethod async def _show_progress(query, user_id: int) -> None`
**Purpose:** Display checking progress
**Parameters:**
- `query`: Telegram callback query
- `user_id` (int): User identifier

**Progress Information:**
- Accounts processed/total
- Current processing rate
- Estimated completion time
- Result statistics

---

## 🛠️ Utilities API

### 📄 utils/account_checker.py

#### `class AccountChecker`
**Purpose:** Main account verification orchestrator

##### `def __init__(self, proxies: List[str], user_id: int)`
**Purpose:** Initialize account checker
**Parameters:**
- `proxies` (List[str]): List of proxy strings
- `user_id` (int): User identifier for progress tracking

**Initialization:**
- Browser manager setup
- Authentication handler creation
- Proxy configuration
- Delay calculation based on proxy count

##### `async def check_accounts(self, accounts: List[str]) -> List[Dict[str, Any]]`
**Purpose:** Check multiple accounts asynchronously
**Parameters:**
- `accounts` (List[str]): List of email:password strings
**Returns:** List of result dictionaries

**Result Dictionary Format:**
```python
{
    'email': str,           # Account email
    'password': str,        # Account password (masked in logs)
    'status': str,          # 'valid', 'invalid', '2fa_required', 'captcha_required', 'error'
    'display_name': str,    # Epic Games display name (if valid)
    'account_id': str,      # Epic Games account ID (if valid)
    'error': str,           # Error message (if error)
    'proxy_used': str,      # Proxy used for checking
    'check_duration': float, # Time taken for check
    'timestamp': str        # Check timestamp
}
```

##### `async def _check_single_account(self, account: str, proxy: str) -> Dict[str, Any]`
**Purpose:** Check individual account
**Parameters:**
- `account` (str): Email:password string
- `proxy` (str): Proxy to use for checking
**Returns:** Result dictionary

**Process:**
1. Browser context creation
2. Epic Games navigation
3. Login attempt
4. Cloudflare challenge handling
5. Account status detection
6. Result compilation

##### `async def _handle_delays(self) -> None`
**Purpose:** Implement human-like delays between checks

**Delay Logic:**
- Single proxy: 3-8 seconds (human-like)
- Multiple proxies: 2-5 seconds (faster rotation)
- Random jitter to avoid patterns
- Adaptive delays based on success rate

### 📄 utils/browser_manager.py

#### `class BrowserManager`
**Purpose:** Advanced browser automation and resource management

##### `def __init__(self, proxies: List[str])`
**Purpose:** Initialize browser manager
**Parameters:**
- `proxies` (List[str]): Available proxies for rotation

**Browser Support:**
- **Camoufox**: Stealth-focused Firefox-based browser
- **Patchright**: Enhanced Chromium with anti-detection
- **Playwright**: Standard Chromium fallback

##### `async def get_browser_context(self, proxy: str) -> BrowserContext`
**Purpose:** Get or create browser context with proxy
**Parameters:**
- `proxy` (str): Proxy string (user:pass@host:port or host:port)
**Returns:** Configured browser context

**Context Configuration:**
- Proxy setup with authentication
- User agent rotation
- Viewport randomization
- Resource blocking (images, fonts, etc.)
- Stealth settings activation

##### `async def cleanup_context(self, context: BrowserContext) -> None`
**Purpose:** Clean up browser context and resources
**Parameters:**
- `context` (BrowserContext): Context to cleanup

**Cleanup Process:**
1. Close all pages in context
2. Clear context storage
3. Remove from active contexts
4. Force garbage collection

##### `async def cleanup_old_browsers(self) -> None`
**Purpose:** Clean up browsers exceeding age limits

**Cleanup Criteria:**
- Browser age > 5 minutes
- Memory usage > 1GB threshold
- Context count > maximum limit
- Resource monitoring triggers

##### `async def force_cleanup(self) -> None`
**Purpose:** Force cleanup of all browser resources

**Emergency Cleanup:**
- Close all browser instances
- Clear all contexts
- Reset resource counters
- Force garbage collection

### 📄 utils/auth_handler.py

#### `class AuthHandler`
**Purpose:** Epic Games authentication and account status detection

##### `def __init__(self, user_id: int)`
**Purpose:** Initialize authentication handler
**Parameters:**
- `user_id` (int): User identifier for logging

##### `async def check_account_status(self, page: Page) -> Dict[str, Any]`
**Purpose:** Determine account status after login attempt
**Parameters:**
- `page` (Page): Browser page after login
**Returns:** Status dictionary

**Status Detection:**
- **Valid**: Successful authentication, account accessible
- **Invalid**: Authentication failed, incorrect credentials
- **2FA Required**: Two-factor authentication needed
- **CAPTCHA Required**: CAPTCHA challenge present
- **Rate Limited**: Temporary access restriction

##### `async def detect_account_state(self, page: Page) -> str`
**Purpose:** Detect current account state from page content
**Parameters:**
- `page` (Page): Browser page to analyze
**Returns:** Account state string

**Detection Methods:**
- URL pattern analysis
- Page title examination
- Element presence checking
- Error message parsing

##### `async def extract_account_info(self, page: Page) -> Dict[str, str]`
**Purpose:** Extract account information for valid accounts
**Parameters:**
- `page` (Page): Authenticated account page
**Returns:** Account information dictionary

**Extracted Information:**
- Display name
- Account ID
- Email verification status
- Account creation date
- Profile picture URL

### 📄 utils/login_handler.py

#### `class LoginHandler`
**Purpose:** Epic Games login process automation

##### `def __init__(self, user_id: int)`
**Purpose:** Initialize login handler
**Parameters:**
- `user_id` (int): User identifier for logging

##### `async def perform_login(self, page: Page, email: str, password: str) -> bool`
**Purpose:** Perform complete login process
**Parameters:**
- `page` (Page): Browser page
- `email` (str): Account email
- `password` (str): Account password
**Returns:** Login success status

**Login Process:**
1. Navigate to Epic Games login page
2. Handle Cloudflare challenges
3. Fill login form
4. Submit credentials
5. Handle post-login challenges
6. Verify login success

##### `async def handle_login_form(self, page: Page, email: str, password: str) -> None`
**Purpose:** Fill and submit login form
**Parameters:**
- `page` (Page): Browser page with login form
- `email` (str): Account email
- `password` (str): Account password

**Form Handling:**
- Wait for form elements
- Clear existing values
- Type credentials with human-like timing
- Handle form validation
- Submit with proper waiting

##### `async def wait_for_login_completion(self, page: Page) -> bool`
**Purpose:** Wait for login process completion
**Parameters:**
- `page` (Page): Browser page
**Returns:** Success status

**Completion Detection:**
- URL change monitoring
- Success element detection
- Error message checking
- Timeout handling

##### `async def detect_login_challenges(self, page: Page) -> List[str]`
**Purpose:** Detect login challenges (CAPTCHA, 2FA, etc.)
**Parameters:**
- `page` (Page): Browser page
**Returns:** List of detected challenges

**Challenge Types:**
- Cloudflare Turnstile
- reCAPTCHA
- Two-factor authentication
- Email verification
- Security questions

---

## 🛡️ Cloudflare Solvers API

### 📄 solvers/turnstile_solver/api_solver.py

#### `def create_app(headless: bool = True, useragent: str = None, debug: bool = False) -> Flask`
**Purpose:** Create Flask API application for Turnstile solving
**Parameters:**
- `headless` (bool): Run browser in headless mode
- `useragent` (str): Custom user agent string
- `debug` (bool): Enable debug mode
**Returns:** Configured Flask application

#### `async def solve_turnstile(request) -> Dict[str, Any]`
**Purpose:** API endpoint for Turnstile challenge solving
**Request Format:**
```json
{
    "site_key": "string",
    "page_url": "string",
    "proxy": "string (optional)"
}
```

**Response Format:**
```json
{
    "success": true,
    "token": "turnstile_token_string",
    "solve_time": 1.23
}
```

### 📄 utils/unified_turnstile_handler.py

#### `class UnifiedTurnstileHandler`
**Purpose:** Unified interface for Turnstile challenge solving

##### `def __init__(self, user_id: int)`
**Purpose:** Initialize Turnstile handler
**Parameters:**
- `user_id` (int): User identifier for logging

##### `async def solve_turnstile(self, page: Page, site_key: str) -> Optional[str]`
**Purpose:** Solve Turnstile challenge on page
**Parameters:**
- `page` (Page): Browser page with challenge
- `site_key` (str): Turnstile site key
**Returns:** Turnstile token or None

**Solving Process:**
1. Challenge detection
2. Solver selection (API/browser)
3. Token extraction
4. Validation
5. Injection into page

##### `async def detect_turnstile_challenge(self, page: Page) -> Optional[str]`
**Purpose:** Detect Turnstile challenge and extract site key
**Parameters:**
- `page` (Page): Browser page
**Returns:** Site key if challenge detected

##### `async def extract_turnstile_token(self, page: Page) -> Optional[str]`
**Purpose:** Extract solved Turnstile token from page
**Parameters:**
- `page` (Page): Browser page
**Returns:** Turnstile token

---

## 📊 Resource Management API

### 📄 utils/resource_monitor.py

#### `class ResourceMonitor`
**Purpose:** System resource monitoring and management

##### `def __init__(self)`
**Purpose:** Initialize resource monitor

##### `async def start_monitoring(self) -> None`
**Purpose:** Start continuous resource monitoring

**Monitoring Metrics:**
- Memory usage (RAM)
- CPU utilization
- Disk space
- Browser process count
- Active context count

##### `async def check_memory_usage(self) -> Dict[str, float]`
**Purpose:** Check current memory usage
**Returns:** Memory statistics dictionary

**Memory Metrics:**
- Total system memory
- Available memory
- Process memory usage
- Memory usage percentage
- Swap usage

##### `async def trigger_cleanup(self) -> None`
**Purpose:** Trigger resource cleanup when thresholds exceeded

**Cleanup Actions:**
- Browser context cleanup
- Temporary file removal
- Memory garbage collection
- Process optimization

---

## ☁️ Cloud Integration API

### 📄 utils/dropbox_uploader.py

#### `class DropboxUploader`
**Purpose:** Dropbox cloud storage integration

##### `def __init__(self)`
**Purpose:** Initialize Dropbox uploader with token management

##### `async def upload_file(self, file_path: str, remote_path: str) -> str`
**Purpose:** Upload file to Dropbox
**Parameters:**
- `file_path` (str): Local file path
- `remote_path` (str): Dropbox destination path
**Returns:** Shared link URL

**Upload Process:**
1. File validation
2. Token refresh if needed
3. Upload with progress tracking
4. Shared link creation
5. Cleanup of local file

##### `async def create_shared_link(self, file_path: str) -> str`
**Purpose:** Create public shared link for file
**Parameters:**
- `file_path` (str): Dropbox file path
**Returns:** Public download URL

##### `async def ensure_folder_exists(self, folder_path: str) -> None`
**Purpose:** Create folder structure if not exists
**Parameters:**
- `folder_path` (str): Dropbox folder path

##### `async def cleanup_old_files(self, max_age_days: int = 7) -> None`
**Purpose:** Remove old files to manage storage
**Parameters:**
- `max_age_days` (int): Maximum file age in days

---

## 📋 API Usage Examples

### Basic Account Checking
```python
# Initialize account checker
proxies = ["proxy1:8080", "proxy2:8080"]
checker = AccountChecker(proxies, user_id=123456)

# Check accounts
accounts = ["user1@example.com:pass1", "user2@example.com:pass2"]
results = await checker.check_accounts(accounts)

# Process results
for result in results:
    if result['status'] == 'valid':
        print(f"Valid account: {result['email']}")
```

### Browser Management
```python
# Initialize browser manager
browser_manager = BrowserManager(proxies)

# Get browser context
context = await browser_manager.get_browser_context("proxy1:8080")

# Use context
page = await context.new_page()
await page.goto("https://example.com")

# Cleanup
await browser_manager.cleanup_context(context)
```

### File Processing
```python
# Initialize file manager
file_manager = FileManager()

# Parse accounts file
accounts = await file_manager.parse_accounts_file("accounts.txt")

# Generate results file
results_path = await file_manager.generate_results_file(results, user_id)
```

---

## 🎯 API Best Practices

### Error Handling
- Always use try-catch blocks for async operations
- Implement proper cleanup in finally blocks
- Log errors with sufficient context
- Provide user-friendly error messages

### Resource Management
- Use context managers for browser operations
- Implement proper cleanup procedures
- Monitor resource usage regularly
- Set appropriate timeouts

### Performance Optimization
- Use connection pooling where possible
- Implement caching for repeated operations
- Optimize database queries
- Use async operations for I/O

### Security Considerations
- Validate all input parameters
- Sanitize file uploads
- Use secure proxy configurations
- Implement rate limiting

---

## 📞 API Support

For API-related questions:
1. Check function docstrings in source code
2. Review this API reference guide
3. Check the Architecture Analysis for system design
4. Create issues for API enhancement requests

---

**Last Updated:** December 2024  
**API Version:** 1.0.0  
**Coverage:** Complete API reference for all public interfaces