#!/usr/bin/env bash

gunicorn wsgi:app --bind 0.0.0.0:$PORT --log-level=debug --workers=4
