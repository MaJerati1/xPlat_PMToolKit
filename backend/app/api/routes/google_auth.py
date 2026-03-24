"""Google OAuth 2.0 routes for Calendar and Drive integration.

Handles the OAuth consent flow:
1. GET /api/auth/google       → Redirects user to Google's consent screen
2. GET /api/auth/google/callback → Receives authorization code, exchanges for access token
3. GET /api/auth/google/status → Check if we have a valid token

Tokens are persisted to the .env file so they survive container restarts.
For production, tokens should be stored per-user in the database with encryption.
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

ENV_FILE_PATH = os.environ.get("ENV_FILE_PATH", ".env")

# In-memory cache (loaded from .env on startup)
_token_store: dict = {}


def _load_tokens_from_env():
    """Load persisted Google tokens from .env file on startup."""
    global _token_store
    if hasattr(settings, 'GOOGLE_ACCESS_TOKEN') and settings.GOOGLE_ACCESS_TOKEN:
        _token_store["access_token"] = settings.GOOGLE_ACCESS_TOKEN
    if hasattr(settings, 'GOOGLE_REFRESH_TOKEN') and settings.GOOGLE_REFRESH_TOKEN:
        _token_store["refresh_token"] = settings.GOOGLE_REFRESH_TOKEN

    # Also try reading directly from .env in case settings didn't pick them up
    if not _token_store.get("access_token"):
        try:
            with open(ENV_FILE_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GOOGLE_ACCESS_TOKEN=') and not line.startswith('#'):
                        val = line.split('=', 1)[1].strip()
                        if val:
                            _token_store["access_token"] = val
                    elif line.startswith('GOOGLE_REFRESH_TOKEN=') and not line.startswith('#'):
                        val = line.split('=', 1)[1].strip()
                        if val:
                            _token_store["refresh_token"] = val
        except FileNotFoundError:
            pass

    if _token_store.get("access_token"):
        logger.info("Loaded Google OAuth tokens from persistent storage")


def _persist_tokens():
    """Save tokens to .env file for persistence across restarts."""
    import re

    try:
        try:
            with open(ENV_FILE_PATH, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            content = ""

        for key in ["GOOGLE_ACCESS_TOKEN", "GOOGLE_REFRESH_TOKEN"]:
            value = _token_store.get(key.replace("GOOGLE_", "").lower(), "")
            # Map store keys to env keys
            if key == "GOOGLE_ACCESS_TOKEN":
                value = _token_store.get("access_token", "")
            elif key == "GOOGLE_REFRESH_TOKEN":
                value = _token_store.get("refresh_token", "")

            pattern = rf'^(#?\s*)?{re.escape(key)}\s*=\s*.*$'
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
            else:
                if not content.endswith("\n"):
                    content += "\n"
                content += f"{key}={value}\n"

        with open(ENV_FILE_PATH, 'w') as f:
            f.write(content)

        logger.info("Google OAuth tokens persisted to .env file")
    except Exception as e:
        logger.warning(f"Failed to persist tokens to .env: {e}")


def _clear_persisted_tokens():
    """Remove tokens from .env file."""
    import re
    try:
        with open(ENV_FILE_PATH, 'r') as f:
            content = f.read()
        for key in ["GOOGLE_ACCESS_TOKEN", "GOOGLE_REFRESH_TOKEN"]:
            content = re.sub(rf'^{re.escape(key)}=.*$', f"{key}=", content, flags=re.MULTILINE)
        with open(ENV_FILE_PATH, 'w') as f:
            f.write(content)
    except Exception as e:
        logger.warning(f"Failed to clear persisted tokens: {e}")


# Load tokens on module import (server startup)
_load_tokens_from_env()


def _get_flow():
    """Create a Google OAuth2 flow object."""
    from google_auth_oauthlib.flow import Flow

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in settings."
        )

    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
        ],
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    return flow


@router.get("/auth/google")
async def google_auth_start():
    """Start the Google OAuth flow."""
    try:
        flow = _get_flow()
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        _token_store["oauth_state"] = state
        return {"auth_url": auth_url, "state": state}
    except Exception as e:
        logger.error(f"OAuth start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/google/callback")
async def google_auth_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
):
    """Handle the OAuth callback from Google."""
    try:
        flow = _get_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        _token_store["access_token"] = credentials.token
        _token_store["refresh_token"] = credentials.refresh_token
        _token_store["token_expiry"] = credentials.expiry.isoformat() if credentials.expiry else None
        _token_store["connected_at"] = datetime.now(timezone.utc).isoformat()

        # Persist to .env for survival across restarts
        _persist_tokens()

        logger.info("Google OAuth connected successfully")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/setup?google=connected")

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/setup?google=error&message={str(e)}")


@router.get("/auth/google/status")
async def google_auth_status():
    """Check the current Google OAuth connection status."""
    has_token = bool(_token_store.get("access_token"))
    return {
        "connected": has_token,
        "connected_at": _token_store.get("connected_at"),
        "token_expiry": _token_store.get("token_expiry"),
        "has_refresh_token": bool(_token_store.get("refresh_token")),
        "scopes": ["drive.readonly", "calendar.readonly"] if has_token else [],
    }


@router.get("/auth/google/token")
async def get_google_token():
    """Get the current Google access token for API calls."""
    token = _token_store.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Google account not connected. Visit /api/auth/google to start the OAuth flow."
        )

    # Check if token needs refresh
    expiry = _token_store.get("token_expiry")
    if expiry:
        try:
            exp_dt = datetime.fromisoformat(expiry)
            if exp_dt < datetime.now(timezone.utc):
                refresh_token = _token_store.get("refresh_token")
                if refresh_token:
                    token = await _refresh_access_token(refresh_token)
                else:
                    raise HTTPException(
                        status_code=401,
                        detail="Google token expired and no refresh token available. Reconnect at /api/auth/google"
                    )
        except (ValueError, TypeError):
            pass

    return {"access_token": token}


@router.delete("/auth/google")
async def google_auth_disconnect():
    """Disconnect Google account by clearing stored tokens."""
    _token_store.clear()
    _clear_persisted_tokens()
    return {"message": "Google account disconnected."}


async def _refresh_access_token(refresh_token: str) -> str:
    """Use the refresh token to get a new access token."""
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to refresh Google token")

    data = resp.json()
    new_token = data["access_token"]

    _token_store["access_token"] = new_token
    if "expires_in" in data:
        from datetime import timedelta
        _token_store["token_expiry"] = (
            datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        ).isoformat()

    # Persist the refreshed token
    _persist_tokens()

    return new_token
