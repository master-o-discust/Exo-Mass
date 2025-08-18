from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import Keyboards
import logging

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    welcome_message = f"""
🤖 **Welcome to Exo Mass Checker!**

Hello {user.first_name}! 👋

This bot helps you check Fortnite account credentials efficiently using Epic Games API with detailed profile data extraction.

**How to use:**
1. 📁 Upload your proxies file (.txt)
2. 👤 Upload your accounts file (.txt in email:pass format)
3. 🚀 Start the checking process
4. 📥 Download your working accounts with profile data

**Features:**
• Direct Epic Games API integration
• Detailed profile data extraction (stats, cosmetics, battle pass info)
• Proxy rotation for better success rates
• Comprehensive account information
• Export working accounts with full details

Ready to get started? Use the menu below! 👇
    """
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=Keyboards.main_menu(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_message = """
📖 **Exo Mass Checker - Help Guide**

**File Formats:**

**Proxies File (.txt):**
```
proxy1.com:8080
proxy2.com:3128
username:password@proxy3.com:8080
http://proxy4.com:8080
```

**Accounts File (.txt):**
```
email1@example.com:password1
email2@example.com:password2
email3@example.com:password3
```

**Commands:**
• `/start` - Start the bot and show main menu
• `/help` - Show this help message
• `/status` - Check current status

**Tips:**
• Use high-quality proxies for better results
• Ensure your files are in the correct format
• The bot uses Epic Games API for accurate results
• Working accounts include detailed profile information
• Results include cosmetics, stats, and battle pass data

**Support:**
If you encounter any issues, please contact the administrator.
    """
    
    await update.message.reply_text(
        help_message,
        reply_markup=Keyboards.back_to_menu(),
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show resource usage"""
    try:
        from utils.resource_monitor import get_resource_info
        
        # Get resource information
        info = await get_resource_info()
        
        if not info.get('monitoring_enabled'):
            status_message = """
📊 **System Status**

⚠️ Resource monitoring is disabled.

To enable monitoring, set `ENABLE_RESOURCE_MONITORING=1` in your environment.
            """
        else:
            process_info = info.get('process', {})
            system_info = info.get('system', {})
            
            memory_mb = process_info.get('memory_mb', 0)
            memory_growth = process_info.get('memory_growth_mb', 0)
            cpu_percent = process_info.get('cpu_percent', 0)
            uptime = process_info.get('uptime_seconds', 0)
            
            system_memory_percent = system_info.get('memory_percent', 0)
            system_cpu_percent = system_info.get('cpu_percent', 0)
            
            # Format uptime
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"
            
            status_message = f"""
📊 **System Status**

**Process Resources:**
🧠 Memory: {memory_mb:.1f}MB (+{memory_growth:.1f}MB growth)
⚡ CPU: {cpu_percent:.1f}%
⏱️ Uptime: {uptime_str}

**System Resources:**
🖥️ System Memory: {system_memory_percent:.1f}%
🔧 System CPU: {system_cpu_percent:.1f}%

**Status:** {'🟢 Healthy' if memory_mb < 512 and system_memory_percent < 80 else '🟡 High Usage' if memory_mb < 1024 else '🔴 Critical'}
            """
        
        await update.message.reply_text(
            status_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await update.message.reply_text(
            "❌ Error retrieving system status. Please try again later."
        )