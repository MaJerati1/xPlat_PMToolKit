"""Google OAuth 2.0 routes for Calendar and Drive integration.

Handles the OAuth consent flow:
1. GET /api/auth/google       → Redirects user to Google's consent screen
2. GET /api/auth/google/callback → Receives authorization code, exchanges for access token
3. GET /api/auth/google/status → Check if we have a valid token

Tokens are stored in-memory for the current session (single-user MVP).
For production, tokens should be stored per-user in the database with encryption.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory token storage (MVP single-user)
# Production: store per-user in DB with encryption
_token_store: dict = {}


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
    """Start the Google OAuth flow.

    Redirects the user to Google's consent screen. After approval,
    Google redirects back to /api/auth/google/callback with an
    authorization code.
    """
    try:
        flow = _get_flow()
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        # Store state for CSRF protection
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
    Stores them in memory for use by the document gathering engine.
    """
    try:
        flow = _get_flow()

        # Exchange authorization code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Store tokens
        _token_store["access_token"] = credentials.token
        _token_store["refresh_token"] = credentials.refresh_token
        _token_store["token_expiry"] = credentials.expiry.isoformat() if credentials.expiry else None
        _token_store["connected_at"] = datetime.now(timezone.utc).isoformat()

        logger.info("Google OAuth connected successfully")

        # Redirect to frontend setup page with success indicator
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
    """Get the current Google access token for API calls.

    Used internally by the frontend to pass to the document gathering endpoint.
    In production, this should be authenticated and per-user.
    """
    token = _token_store.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Google account not connected. Visit /api/auth/google to start the OAuth flow."
        )

    # Check if token needs refresh
    expiry = _token_store.get("token_expiry")
    if expiry:
        from datetime import datetime
        try:
            exp_dt = datetime.fromisoformat(expiry)
            if exp_dt < datetime.now(timezone.utc):
                # Try to refresh
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

    # Update store
    _token_store["access_token"] = new_token
    if "expires_in" in data:
        from datetime import timedelta
        _token_store["token_expiry"] = (
            datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        ).isoformat()

    return new_token
