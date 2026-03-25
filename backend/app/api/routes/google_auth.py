"""Google OAuth 2.0 routes for Calendar and Drive integration.

Handles the OAuth consent flow:
1. GET /api/auth/google       → Redirects user to Google's consent screen
2. GET /api/auth/google/callback → Receives authorization code, exchanges for access token
3. GET /api/auth/google/status → Check if we have a valid token

Tokens are persisted to a JSON file so they survive container restarts.
For production, tokens should be stored per-user in the database with encryption.
"""

import json
import os
import logging
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Persist tokens to a JSON file in the project root (mounted volume)
# This survives container restarts because ./:/project-root is a bind mount
TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "/project-root/.google_tokens.json")

# In-memory cache (loaded from file on startup)
_token_store: dict = {}


def _load_tokens():
    """Load tokens from the JSON file into memory."""
    global _token_store
    try:
        path = Path(TOKEN_FILE)
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)
            if data.get("access_token"):
                _token_store.update(data)
                logger.info("Google OAuth tokens loaded from %s", TOKEN_FILE)
            else:
                logger.info("Token file exists but no access token found")
        else:
            logger.info("No token file found at %s — Google not connected", TOKEN_FILE)
    except Exception as e:
        logger.warning("Failed to load Google tokens: %s", e)


def _save_tokens():
    """Persist the in-memory tokens to the JSON file."""
    try:
        data = {
            "access_token": _token_store.get("access_token", ""),
            "refresh_token": _token_store.get("refresh_token", ""),
            "token_expiry": _token_store.get("token_expiry", ""),
            "connected_at": _token_store.get("connected_at", ""),
        }
        path = Path(TOKEN_FILE)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info("Google OAuth tokens saved to %s", TOKEN_FILE)
    except Exception as e:
        logger.warning("Failed to save Google tokens: %s", e)


def _delete_token_file():
    """Remove the token file on disconnect."""
    try:
        path = Path(TOKEN_FILE)
        if path.exists():
            path.unlink()
            logger.info("Token file deleted: %s", TOKEN_FILE)
    except Exception as e:
        logger.warning("Failed to delete token file: %s", e)


# Load tokens on module import (server startup)
_load_tokens()


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
    """Handle the OAuth callback from Google.

    Exchanges the authorization code for access and refresh tokens.
    Persists them to disk for survival across container restarts.
    """
    try:
        flow = _get_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        _token_store["access_token"] = credentials.token
        _token_store["refresh_token"] = credentials.refresh_token
        _token_store["token_expiry"] = credentials.expiry.isoformat() if credentials.expiry else None
        _token_store["connected_at"] = datetime.now(timezone.utc).isoformat()

        # Persist to file
        _save_tokens()

        logger.info("Google OAuth connected successfully")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/setup?google=connected")

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/setup?google=error&message={str(e)}")


@router.get("/auth/google/status")
async def google_auth_status():
    """Check the current Google OAuth connection status."""
    if not _token_store.get("access_token"):
        _load_tokens()

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
    """Get the current Google access token for API calls.

    Automatically refreshes expired tokens using the refresh token.
    """
    if not _token_store.get("access_token"):
        _load_tokens()

    token = _token_store.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Google account not connected. Visit /api/auth/google to start the OAuth flow."
        )

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
    _delete_token_file()
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

    _save_tokens()
    return new_token
