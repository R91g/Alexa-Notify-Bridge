#!/usr/bin/with-contenv bashio

# ─── Read configuration from Home Assistant ─────────────────────────────────

if bashio::config.has_value 'alexa_client_id'; then
    export ALEXA_CLIENT_ID="$(bashio::config 'alexa_client_id')"
fi

if bashio::config.has_value 'alexa_client_secret'; then
    export ALEXA_CLIENT_SECRET="$(bashio::config 'alexa_client_secret')"
fi

# API Key (optional — only export if the user has set a value)
if bashio::config.has_value 'api_key'; then
    export API_KEY="$(bashio::config 'api_key')"
fi

# Region → Proactive Events URL mapping
REGION="$(bashio::config 'region')"
case "${REGION}" in
    NA)
        export PROACTIVE_EVENTS_URL="https://api.amazonalexa.com/v1/proactiveEvents/stages/development"
        ;;
    EU)
        export PROACTIVE_EVENTS_URL="https://api.eu.amazonalexa.com/v1/proactiveEvents/stages/development"
        ;;
    FE)
        export PROACTIVE_EVENTS_URL="https://api.fe.amazonalexa.com/v1/proactiveEvents/stages/development"
        ;;
esac

# Log level
export LOG_LEVEL="$(bashio::config 'log_level')"

# Default notification expiry (hours)
export DEFAULT_EXPIRY_HOURS="$(bashio::config 'default_expiry_hours')"

# Anti-duplicate debounce filter (seconds)
if bashio::config.has_value 'debounce_seconds'; then
    export DEBOUNCE_SECONDS="$(bashio::config 'debounce_seconds')"
fi

# ─── Start the bridge ───────────────────────────────────────────────────────

bashio::log.info "Starting Alexa Notify Bridge..."
bashio::log.info "Region: ${REGION}"
bashio::log.info "Log level: ${LOG_LEVEL}"

cd /app || exit 1
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8080