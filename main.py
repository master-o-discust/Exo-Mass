#!/usr/bin/env python3
"""
Exo Mass Checker - Telegram Bot for Fortnite Account Checking
"""

import asyncio
import logging
import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import Update, BotCommand
from telegram.ext import ContextTypes

# Import handlers
from handlers.start_handler import start_command, help_command, status_command
from handlers.file_handler import FileHandler
from handlers.callback_handler import CallbackHandler

# Import configuration
from config.settings import (
    BOT_TOKEN, TEMP_DIR, DATA_DIR,
    ENABLE_TURNSTILE_SERVICE, TURNSTILE_SERVICE_HOST, TURNSTILE_SERVICE_PORT,
    TURNSTILE_SERVICE_THREADS, USE_ENHANCED_BROWSER, PREFERRED_BROWSER_TYPE,
    ENABLE_BOTSFORGE_SERVICE, BOTSFORGE_SERVICE_HOST, BOTSFORGE_SERVICE_PORT
)

# API key management is now handled by individual solvers

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again or contact support."
            )
        except:
            pass

async def setup_bot_commands(application):
    """Set up bot commands for the Telegram menu"""
    commands = [
        BotCommand("start", "Start the bot and show main menu"),
        BotCommand("status", "Show system resource usage"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands set up successfully!")

# Service startup functions removed - these are separate API servers that run independently

async def refresh_dropbox_token(context):
    """Background job to refresh Dropbox token every 3 hours"""
    try:
        from config import settings as _settings
        if _settings.DROPBOX_ENABLED:
            from utils.dropbox_uploader import DropboxTokenManager
            token = await DropboxTokenManager.force_refresh()
            if token:
                logger.info("🔄 Dropbox token refreshed successfully (scheduled refresh)")
            else:
                logger.warning("⚠️ Failed to refresh Dropbox token (scheduled refresh)")
    except Exception as e:
        logger.error(f"❌ Error during scheduled Dropbox token refresh: {e}")

async def initialize_all_systems():
    """Initialize all systems including solvers and resource monitoring"""
    logger.info("🚀 Initializing Mass-checker systems...")
    
    # Initialize resource monitoring
    from utils.resource_monitor import resource_monitor, add_resource_alert_callback
    
    # Add alert callback for resource issues
    async def resource_alert_handler(alert):
        logger.warning(f"🚨 Resource Alert: {alert.message}")
        if alert.alert_type.endswith('_critical'):
            logger.error("🔧 Consider reducing concurrent checks or restarting the bot")
    
    add_resource_alert_callback(resource_alert_handler)
    
    # Start resource monitoring in background
    asyncio.create_task(resource_monitor.start_monitoring())

    # Initialize Dropbox token and folders early so uploads work immediately
    try:
        from config import settings as _settings
        if _settings.DROPBOX_ENABLED:
            from utils.dropbox_uploader import DropboxTokenManager, DropboxUploader
            token = await DropboxTokenManager.get_access_token()
            if token:
                base_folder = _settings.DROPBOX_BASE_FOLDER.strip('/')
                # Ensure base and common subfolders exist
                common_folders = [
                    base_folder,
                    f"{base_folder}/screenshots",
                    f"{base_folder}/auth_tokens",
                    f"{base_folder}/results",
                    f"{base_folder}/emails",
                    f"{base_folder}/proxies",
                    f"{base_folder}/user_uploads",
                    f"{base_folder}/summaries",
                ]
                for folder in common_folders:
                    await DropboxUploader.ensure_folder_recursive(token, folder)
                logger.info("✅ Dropbox access token initialized and base folders verified")
            else:
                logger.warning("⚠️ Dropbox enabled but failed to initialize access token. Uploads may fail until credentials are fixed.")
    except Exception as e:
        logger.warning(f"⚠️ Dropbox initialization skipped due to error: {e}")
    
    # Initialize all solvers (each solver handles its own API key generation)
    from utils.solver_manager import initialize_solvers
    solver_status = await initialize_solvers()
    
    # Service startup removed - these are separate API servers that run independently
    
    logger.info("✅ All systems initialized successfully!")
    return solver_status

def main():
    """Start the bot"""
    # Check if token is provided
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Please set it in your .env file")
        return
    
    # Create directories
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Initialize all systems at startup
    application.job_queue.run_once(
        lambda context: asyncio.create_task(initialize_all_systems()), 
        when=1
    )
    
    # Set up bot commands for menu
    application.job_queue.run_once(
        lambda context: setup_bot_commands(application), 
        when=2
    )
    
    # Schedule Dropbox token refresh every 3 hours
    application.job_queue.run_repeating(
        refresh_dropbox_token,
        interval=3 * 60 * 60,  # 3 hours in seconds
        first=3 * 60 * 60,     # First refresh after 3 hours
        name="dropbox_token_refresh"
    )
    logger.info("🔄 Dropbox token refresh scheduled every 3 hours")
    
    # Note: Turnstile service is now started in initialize_all_systems()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # File upload handler
    application.add_handler(MessageHandler(
        filters.Document.ALL, 
        FileHandler.handle_document
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(CallbackHandler.handle_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🤖 Starting Exo Mass Checker Bot with Enhanced Turnstile Bypass...")
    logger.info(f"🔧 Enhanced Browser: {USE_ENHANCED_BROWSER} ({PREFERRED_BROWSER_TYPE})")
    logger.info(f"🛡️ Turnstile Service: {ENABLE_TURNSTILE_SERVICE}")
    if ENABLE_TURNSTILE_SERVICE:
        logger.info(f"🌐 Turnstile API: http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}")
    logger.info(f"🔧 BotsForge Service: {ENABLE_BOTSFORGE_SERVICE}")
    if ENABLE_BOTSFORGE_SERVICE:
        logger.info(f"🌐 BotsForge API: http://{BOTSFORGE_SERVICE_HOST}:{BOTSFORGE_SERVICE_PORT}")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")

if __name__ == '__main__':
    main()