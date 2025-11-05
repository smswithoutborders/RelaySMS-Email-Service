#!/bin/bash

. venv/bin/activate

set -a
source .env
set +a

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8080}

uvicorn app:app --host "$HOST" --port "$PORT" --workers 4 --proxy-headers --forwarded-allow-ips='*'
