import asyncio
import logging
import os
import secrets
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("alexa-notify-bridge")

# ─── Alexa credentials ──────────────────────────────────────────────────────

ALEXA_CLIENT_ID = os.getenv("ALEXA_CLIENT_ID")
ALEXA_CLIENT_SECRET = os.getenv("ALEXA_CLIENT_SECRET")

# ─── API Key security (optional, recommended) ───────────────────────────────
# If API_KEY is set in .env, requests must include it in the "x-api-key" header.

API_KEY = os.getenv("API_KEY")
api_key_header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)

if not API_KEY:
    logger.warning(
        "API_KEY is not set. The /notify endpoint is open without authentication. "
        "Set API_KEY in your .env file to protect it."
    )


async def verify_api_key(key: str = Security(api_key_header_scheme)):
    """Validate the API key if one is configured."""
    if API_KEY:
        if not key or not secrets.compare_digest(key, API_KEY):
            raise HTTPException(
                status_code=403,
                detail="Invalid or missing API key.",
            )
    return key


# ─── Amazon endpoints ───────────────────────────────────────────────────────

TOKEN_URL = "https://api.amazon.com/auth/o2/token"

PROACTIVE_EVENTS_URL = os.getenv(
    "PROACTIVE_EVENTS_URL",
    "https://api.eu.amazonalexa.com/v1/proactiveEvents/stages/development",
)

# Amazon Proactive Events requires expiry to be between 5 minutes and 24 hours.
MIN_EXPIRY_HOURS = 5 / 60  # 5 minutes (~0.0833 hours)
MAX_EXPIRY_HOURS = 24.0   # 24 hours


def clamp_expiry_hours(hours: float) -> float:
    """Clamp expiry to Amazon's allowed range (5 minutes to 24 hours)."""
    return max(MIN_EXPIRY_HOURS, min(MAX_EXPIRY_HOURS, hours))


_raw_default_expiry = float(os.getenv("DEFAULT_EXPIRY_HOURS", "24"))
DEFAULT_EXPIRY_HOURS = clamp_expiry_hours(_raw_default_expiry)
if DEFAULT_EXPIRY_HOURS != _raw_default_expiry:
    _adjusted_desc = "5 minutes (minimum)" if DEFAULT_EXPIRY_HOURS == MIN_EXPIRY_HOURS else "24 hours (maximum)"
    logger.warning(
        "Configured DEFAULT_EXPIRY_HOURS (%s) is outside Amazon's limits (5 min to 24h). Adjusted to %s.",
        _raw_default_expiry,
        _adjusted_desc,
    )

# ─── Debounce filter (anti-duplicate notifications) ──────────────────────────
# Minimum time in seconds to prevent sending identical consecutive notifications.
# 0 = disabled. Can be overridden per request via debounce_seconds.

_raw_debounce = float(os.getenv("DEBOUNCE_SECONDS", "0"))
DEBOUNCE_SECONDS = max(0.0, _raw_debounce)


class DebounceFilter:
    """In-memory cache preventing identical notifications from sounding repeatedly."""

    def __init__(self, max_entries: int = 50):
        self._history: dict[str, float] = {}
        self._max_entries = max_entries
        self._lock = asyncio.Lock()

    async def is_duplicate(self, text: str, window_seconds: float) -> bool:
        """Check if identical text was received within window_seconds. If not, record it."""
        if window_seconds <= 0:
            return False

        async with self._lock:
            now = time.time()
            cutoff = now - max(window_seconds, 3600.0)
            self._history = {k: ts for k, ts in self._history.items() if ts > cutoff}

            last_time = self._history.get(text)
            if last_time is not None and (now - last_time) < window_seconds:
                return True

            self._history[text] = now
            return False


debounce_filter = DebounceFilter()

# ─── Message length limits ───────────────────────────────────────────────────
# Amazon limits the MessageAlert creator.name field to 256 characters.

MAX_MESSAGE_CHARS = 256
TRUNCATE_CHARS = 253  # Leaves 3 chars for "..."


def process_message_text(text: str) -> tuple[str, bool]:
    """Strip whitespace and truncate message to 256 chars if it exceeds Amazon's limit.

    Returns (processed_text, was_truncated).
    """
    clean = text.strip()
    if len(clean) > MAX_MESSAGE_CHARS:
        truncated = clean[:TRUNCATE_CHARS] + "..."
        logger.warning(
            "Notification message exceeded Amazon's %d char limit (%d chars). "
            "Truncated automatically to: '%s'",
            MAX_MESSAGE_CHARS,
            len(clean),
            truncated,
        )
        return truncated, True
    return clean, False


# ─── Request model ──────────────────────────────────────────────────────────


class NotificationRequest(BaseModel):
    """Payload expected by the POST /notify endpoint."""

    creator_name: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The text that Alexa will read aloud (the 'creator' trick). "
        "If longer than 256 chars, it is automatically truncated to 253 + '...'.",
    )
    urgency: Literal["URGENT"] = "URGENT"
    expiry_hours: float | None = Field(
        default=None,
        description="Hours until the notification expires (5 min to 24h). "
        "Values under 5 min are adjusted to 5 min; values over 24h are capped at 24h. "
        "If omitted, uses the DEFAULT_EXPIRY_HOURS setting (default: 24h).",
    )
    debounce_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Optional per-request debounce window in seconds. Overrides DEBOUNCE_SECONDS.",
    )


# ─── Token cache ────────────────────────────────────────────────────────────


class TokenCache:
    """Simple in-memory cache for the Amazon LWA access token.

    Note: the cache is per-process. If you run multiple Uvicorn workers,
    each worker will maintain its own token cache.
    """

    def __init__(self):
        self.token: str | None = None
        self.expires_at: float = 0


token_cache = TokenCache()


async def get_access_token(force_refresh: bool = False) -> str:
    """Obtain a valid Amazon LWA access token, using the cache when possible."""
    now = time.time()

    if not force_refresh and token_cache.token and token_cache.expires_at > now:
        return token_cache.token

    if not ALEXA_CLIENT_ID or not ALEXA_CLIENT_SECRET:
        logger.error("ALEXA_CLIENT_ID or ALEXA_CLIENT_SECRET not configured.")
        raise HTTPException(
            status_code=500,
            detail="Alexa client credentials not configured. Set them in .env.",
        )

    async with httpx.AsyncClient() as client:
        data = {
            "grant_type": "client_credentials",
            "client_id": ALEXA_CLIENT_ID,
            "client_secret": ALEXA_CLIENT_SECRET,
            "scope": "alexa::proactive_events",
        }
        try:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to obtain Amazon access token: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get access token: {exc}",
            )

        token_data = response.json()
        token_cache.token = token_data["access_token"]
        # Subtract 60 s as a safety margin for network delays
        token_cache.expires_at = now + token_data.get("expires_in", 3600) - 60

        logger.info("Amazon access token refreshed successfully.")
        return token_cache.token


# ─── Rate limiter ───────────────────────────────────────────────────────────


class RateLimiter:
    """Prevents flooding Amazon's API by limiting requests in a sliding time window."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 10.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def check(self):
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            # Remove timestamps outside the window
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit: max {self.max_requests} notifications "
                    f"per {self.window_seconds:.0f}s. Please try again later.",
                )
            self._timestamps.append(now)


rate_limiter = RateLimiter(max_requests=10, window_seconds=10.0)


# ─── Retry configuration ───────────────────────────────────────────────────

MAX_RETRIES = 1
RETRY_DELAY_S = 2.0


# ─── Notification history (in-memory, last N entries) ──────────────────────

MAX_HISTORY = 50
notification_history: deque[dict] = deque(maxlen=MAX_HISTORY)


# ─── App lifespan (startup / shutdown) ──────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks before the app begins accepting requests."""
    if ALEXA_CLIENT_ID and ALEXA_CLIENT_SECRET:
        try:
            await get_access_token()
            logger.info(
                "Startup check passed: Amazon credentials are valid."
            )
        except Exception as exc:
            logger.error(
                "Startup check FAILED: could not authenticate with Amazon. "
                "Verify ALEXA_CLIENT_ID and ALEXA_CLIENT_SECRET in your .env file. "
                "Error: %s",
                exc,
            )
    else:
        logger.error(
            "ALEXA_CLIENT_ID and/or ALEXA_CLIENT_SECRET not set in .env. "
            "The bridge will NOT be able to send notifications."
        )
    yield


# ─── FastAPI app ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Alexa Notify Bridge",
    docs_url=None,   # Disable Swagger UI in production
    redoc_url=None,   # Disable ReDoc in production
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors clearly so they are visible in Docker logs."""
    # Strip pydantic's 'ctx' which may contain non-serializable exception objects
    errors = [
        {k: v for k, v in err.items() if k != "ctx"} for err in exc.errors()
    ]
    logger.error("Request validation failed: %s", errors)
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(errors)},
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Health-check endpoint for monitoring and Docker HEALTHCHECK."""
    return {"status": "ok"}


@app.get("/history")
async def get_history(
    limit: int = 50,
    _api_key: str = Depends(verify_api_key),
):
    """Return the last notifications sent (most recent first, in-memory only)."""
    safe_limit = max(1, min(limit, MAX_HISTORY))
    items = list(notification_history)[:safe_limit]
    return {
        "count": len(items),
        "total": len(notification_history),
        "notifications": items,
    }


@app.post("/notify")
async def notify(
    request: NotificationRequest,
    _api_key: str = Depends(verify_api_key),
):
    """Receive a local request and forward it as a proactive event to Alexa."""
    raw_text = request.creator_name.strip()
    if not raw_text:
        raise HTTPException(
            status_code=422,
            detail="creator_name cannot be empty or whitespace only.",
        )

    message_text, is_truncated = process_message_text(raw_text)

    # Check debounce filter before rate limiter
    effective_debounce = (
        request.debounce_seconds
        if request.debounce_seconds is not None
        else DEBOUNCE_SECONDS
    )
    if await debounce_filter.is_duplicate(message_text, effective_debounce):
        logger.info(
            "Debounced duplicate notification within %.1fs: '%s'",
            effective_debounce,
            message_text,
        )
        return {
            "status": "ignored",
            "debounced": True,
            "message": "Duplicate notification ignored (debounced)",
        }

    # Check rate limit before doing any work
    await rate_limiter.check()

    token = await get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Build ISO 8601 timestamps
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    raw_hours = request.expiry_hours if request.expiry_hours is not None else DEFAULT_EXPIRY_HOURS
    hours = clamp_expiry_hours(raw_hours)
    if request.expiry_hours is not None and hours != raw_hours:
        adjusted_desc = (
            "5 minutes (minimum allowed)"
            if hours == MIN_EXPIRY_HOURS
            else "24 hours (maximum allowed)"
        )
        logger.warning(
            "Notification expiry of %s hours is outside Amazon's limits (5 min to 24h). Adjusted to %s.",
            raw_hours,
            adjusted_desc,
        )
    expiry_dt = now + timedelta(hours=hours)
    expiry = expiry_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{expiry_dt.microsecond // 1000:03d}Z"

    reference_id = str(uuid.uuid4())

    event_payload = {
        "timestamp": timestamp,
        "referenceId": reference_id,
        "expiryTime": expiry,
        "event": {
            "name": "AMAZON.MessageAlert.Activated",
            "payload": {
                "state": {
                    "status": "UNREAD",
                    "freshness": "NEW",
                },
                "messageGroup": {
                    "creator": {
                        "name": message_text,
                    },
                    "count": 1,
                    "urgency": request.urgency,
                },
            },
        },
        "relevantAudience": {
            "type": "Multicast",
            "payload": {},
        },
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(1 + MAX_RETRIES):
            try:
                response = await client.post(
                    PROACTIVE_EVENTS_URL, headers=headers, json=event_payload
                )
                response.raise_for_status()
                break  # Success — exit retry loop
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401 and attempt < MAX_RETRIES:
                    logger.warning(
                        "Amazon access token rejected (401), refreshing token and retrying..."
                    )
                    token = await get_access_token(force_refresh=True)
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                if exc.response.status_code >= 500 and attempt < MAX_RETRIES:
                    logger.warning(
                        "Amazon API error (%s), retrying in %.0fs...",
                        exc.response.status_code,
                        RETRY_DELAY_S,
                    )
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue
                logger.error(
                    "Alexa API rejected the request (%s): %s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=f"Alexa API error: {exc.response.text}",
                )
            except httpx.HTTPError as exc:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "Network error, retrying in %.0fs: %s",
                        RETRY_DELAY_S,
                        exc,
                    )
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue
                logger.error("Network error sending proactive event: %s", exc)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to send proactive event: {exc}",
                )

    # Store in history (most recent first)
    history_entry = {
        "timestamp": timestamp,
        "message": message_text,
        "expiry_hours": round(hours, 2),
        "reference_id": reference_id,
    }
    if is_truncated:
        history_entry["truncated"] = True
    notification_history.appendleft(history_entry)

    logger.info("Notification sent: %s", message_text)
    response_data = {
        "status": "success",
        "message": "Notification sent successfully",
        "reference_id": reference_id,
        "expiry_hours": round(hours, 2),
    }
    if is_truncated:
        response_data["truncated"] = True
    return response_data
