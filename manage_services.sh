#!/bin/bash

# Service Management Script for Exo Mass Checker
# Usage: ./manage_services.sh [start|stop|restart|status|logs]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"
TURNSTILE_PID_FILE="$LOGS_DIR/turnstile.pid"
BOT_PID_FILE="$LOGS_DIR/bot.pid"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

start_services() {
    echo "🚀 Starting Exo Mass Checker services..."
    
    # Start Turnstile API Server
    echo "📡 Starting Turnstile API Server..."
    cd "$SCRIPT_DIR"
    nohup python start_turnstile_api.py > "$LOGS_DIR/turnstile_server.log" 2>&1 &
    echo $! > "$TURNSTILE_PID_FILE"
    echo "✅ Turnstile API Server started (PID: $(cat $TURNSTILE_PID_FILE))"
    
    # Wait a moment for server to initialize
    sleep 3
    
    # Start Telegram Bot
    echo "🤖 Starting Telegram Bot..."
    nohup python main.py > "$LOGS_DIR/telegram_bot.log" 2>&1 &
    echo $! > "$BOT_PID_FILE"
    echo "✅ Telegram Bot started (PID: $(cat $BOT_PID_FILE))"
    
    echo "🎉 All services started successfully!"
    echo "📋 Use './manage_services.sh status' to check service status"
    echo "📄 Use './manage_services.sh logs' to view logs"
}

stop_services() {
    echo "🛑 Stopping Exo Mass Checker services..."
    
    # Stop Telegram Bot
    if [ -f "$BOT_PID_FILE" ]; then
        BOT_PID=$(cat "$BOT_PID_FILE")
        if kill -0 "$BOT_PID" 2>/dev/null; then
            echo "🤖 Stopping Telegram Bot (PID: $BOT_PID)..."
            kill "$BOT_PID"
            rm "$BOT_PID_FILE"
            echo "✅ Telegram Bot stopped"
        else
            echo "⚠️ Telegram Bot not running"
            rm -f "$BOT_PID_FILE"
        fi
    else
        echo "⚠️ No Telegram Bot PID file found"
    fi
    
    # Stop Turnstile API Server
    if [ -f "$TURNSTILE_PID_FILE" ]; then
        TURNSTILE_PID=$(cat "$TURNSTILE_PID_FILE")
        if kill -0 "$TURNSTILE_PID" 2>/dev/null; then
            echo "📡 Stopping Turnstile API Server (PID: $TURNSTILE_PID)..."
            kill "$TURNSTILE_PID"
            rm "$TURNSTILE_PID_FILE"
            echo "✅ Turnstile API Server stopped"
        else
            echo "⚠️ Turnstile API Server not running"
            rm -f "$TURNSTILE_PID_FILE"
        fi
    else
        echo "⚠️ No Turnstile API Server PID file found"
    fi
    
    echo "🎯 All services stopped"
}

check_status() {
    echo "📊 Exo Mass Checker Service Status:"
    echo "=================================="
    
    # Check Turnstile API Server
    if [ -f "$TURNSTILE_PID_FILE" ]; then
        TURNSTILE_PID=$(cat "$TURNSTILE_PID_FILE")
        if kill -0 "$TURNSTILE_PID" 2>/dev/null; then
            echo "📡 Turnstile API Server: ✅ RUNNING (PID: $TURNSTILE_PID)"
        else
            echo "📡 Turnstile API Server: ❌ STOPPED (stale PID file)"
            rm -f "$TURNSTILE_PID_FILE"
        fi
    else
        echo "📡 Turnstile API Server: ❌ STOPPED"
    fi
    
    # Check Telegram Bot
    if [ -f "$BOT_PID_FILE" ]; then
        BOT_PID=$(cat "$BOT_PID_FILE")
        if kill -0 "$BOT_PID" 2>/dev/null; then
            echo "🤖 Telegram Bot: ✅ RUNNING (PID: $BOT_PID)"
        else
            echo "🤖 Telegram Bot: ❌ STOPPED (stale PID file)"
            rm -f "$BOT_PID_FILE"
        fi
    else
        echo "🤖 Telegram Bot: ❌ STOPPED"
    fi
    
    echo ""
    echo "📄 Log files:"
    echo "   Turnstile Server: $LOGS_DIR/turnstile_server.log"
    echo "   Telegram Bot: $LOGS_DIR/telegram_bot.log"
}

show_logs() {
    echo "📄 Recent logs from both services:"
    echo "=================================="
    
    if [ -f "$LOGS_DIR/turnstile_server.log" ]; then
        echo ""
        echo "📡 Turnstile API Server (last 10 lines):"
        echo "----------------------------------------"
        tail -10 "$LOGS_DIR/turnstile_server.log"
    fi
    
    if [ -f "$LOGS_DIR/telegram_bot.log" ]; then
        echo ""
        echo "🤖 Telegram Bot (last 10 lines):"
        echo "--------------------------------"
        tail -10 "$LOGS_DIR/telegram_bot.log"
    fi
}

case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        echo "🔄 Restarting services..."
        stop_services
        sleep 2
        start_services
        ;;
    status)
        check_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start both Turnstile API Server and Telegram Bot"
        echo "  stop    - Stop both services"
        echo "  restart - Restart both services"
        echo "  status  - Check service status"
        echo "  logs    - Show recent logs from both services"
        exit 1
        ;;
esac