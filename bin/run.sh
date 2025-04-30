#!/usr/bin/env bash
cd "$(dirname "$0")/.."
gunicorn wsgi:app --bind 0.0.0.0:$PORT --log-level=debug --workers=4 &
python dbot/bot.py
