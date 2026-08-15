#!/bin/sh
set -eu
mkdir -p /data/exports
cat > /app/app/static/env.js <<EOF
window.FITNESS_API_KEY = "${FITNESS_API_KEY:-}";
EOF
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
