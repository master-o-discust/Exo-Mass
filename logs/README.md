# Exo Mass Checker - Logs Directory

This directory contains log files for the Exo Mass Checker services.

## Log Files

- **`turnstile_server.log`** - Turnstile API Server logs
- **`telegram_bot.log`** - Telegram Bot logs
- **`turnstile.pid`** - Process ID file for Turnstile API Server
- **`bot.pid`** - Process ID file for Telegram Bot

## Service Management

Use the `manage_services.sh` script in the parent directory to control the services:

```bash
# Start both services
./manage_services.sh start

# Stop both services
./manage_services.sh stop

# Restart both services
./manage_services.sh restart

# Check service status
./manage_services.sh status

# View recent logs
./manage_services.sh logs
```

## Manual Log Viewing

```bash
# View Turnstile API Server logs
tail -f logs/turnstile_server.log

# View Telegram Bot logs
tail -f logs/telegram_bot.log

# View both logs simultaneously
tail -f logs/*.log
```

## Log Rotation

Logs will grow over time. Consider implementing log rotation if running for extended periods:

```bash
# Archive current logs
mv logs/turnstile_server.log logs/turnstile_server.log.$(date +%Y%m%d_%H%M%S)
mv logs/telegram_bot.log logs/telegram_bot.log.$(date +%Y%m%d_%H%M%S)

# Restart services to create new log files
./manage_services.sh restart
```