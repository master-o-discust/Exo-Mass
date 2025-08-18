#!/bin/bash
# Check status of all Mass Checker services

echo "=== EXOMASS CHECKER SERVICE STATUS ==="
echo ""

# Check processes
echo "🔍 Running Processes:"
echo "BotsForge (app.py): $(ps aux | grep 'python app.py' | grep -v grep | wc -l) instance(s)"
echo "Turnstile (start_turnstile_api.py): $(ps aux | grep 'start_turnstile_api.py' | grep -v grep | wc -l) instance(s)"
echo "Telegram Bot (main.py): $(ps aux | grep 'python main.py' | grep -v grep | wc -l) instance(s)"
echo ""

# Check ports
echo "🌐 Port Status:"
if curl -s http://localhost:5033 >/dev/null 2>&1; then
    echo "Port 5033 (BotsForge): ✅ Running"
else
    echo "Port 5033 (BotsForge): ❌ Not responding"
fi

if curl -s http://localhost:5000 >/dev/null 2>&1; then
    echo "Port 5000 (Turnstile): ✅ Running"
else
    echo "Port 5000 (Turnstile): ❌ Not responding"
fi
echo ""

# Check log files
echo "📊 Recent Activity (last 3 lines from each log):"
echo ""
echo "--- BotsForge Server ---"
if [ -f logs/botsforge.log ]; then
    tail -3 logs/botsforge.log
else
    echo "❌ Log file not found"
fi
echo ""

echo "--- Turnstile Server ---"
if [ -f logs/turnstile.log ]; then
    tail -3 logs/turnstile.log
else
    echo "❌ Log file not found"
fi
echo ""

echo "--- Telegram Bot ---"
if [ -f logs/telegram_bot.log ]; then
    tail -3 logs/telegram_bot.log
else
    echo "❌ Log file not found"
fi
echo ""

echo "=== END STATUS REPORT ==="