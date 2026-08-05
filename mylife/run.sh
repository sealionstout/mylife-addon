#!/usr/bin/with-contenv bashio
# Read add-on options into environment variables the app reads.
export HA_URL="http://supervisor/core"
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export BL101_DOMAIN="$(bashio::config 'bl101_domain')"
export HA_POLL_SECONDS="$(bashio::config 'ha_poll_seconds')"
export BL101_POLL_HOURS="$(bashio::config 'bl101_poll_hours')"
# Emit kids as a compact "Name:Size,Name:Size" string (robust vs. JSON quoting)
export KIDS_CSV="$(bashio::config 'kids | map(.name + ":" + .size) | join(",")')"
export DB_PATH="/share/mylife.db"

bashio::log.info "Starting myLife backend on :8000 (HA via supervisor proxy)"
cd /app
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
