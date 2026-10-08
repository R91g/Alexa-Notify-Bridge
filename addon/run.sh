#!/usr/bin/with-contenv bashio

# ─── Read configuration from Home Assistant ─────────────────────────────────

export ALEXA_CLIENT_ID="$(bashio::config 'alexa_client_id')"
export ALEXA_CLIENT_SECRET="$(bashio::config 'alexa_client_secret')"

# API Key (optional — only export if the user has set a value)
API_KEY_VALUE="$(bashio::config 'api_key')"
if bashio::var.has_value "${API_KEY_VALUE}"; then
    export API_KEY="${API_KEY_VALUE}"
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

# ─── Start the bridge ───────────────────────────────────────────────────────

bashio::log.info "Starting Alexa Notify Bridge..."
bashio::log.info "Region: ${REGION}"
bashio::log.info "Log level: ${LOG_LEVEL}"

cd /app || exit 1
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
