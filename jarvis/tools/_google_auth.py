"""
Shared Google OAuth helper.
Credentials JSON downloaded from Google Cloud Console → data/google_credentials.json
Token auto-saved to data/google_token.json after first browser auth.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
CREDS_PATH = _ROOT / "data" / "google_credentials.json"
TOKEN_PATH = _ROOT / "data" / "google_token.json"

# Least privilege (DPIA action A4): read mail, send mail, manage events only.
# No gmail.modify (no label changes), no full calendar (no ACL/settings), no contacts.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]

_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def granted_scopes(path: Path = TOKEN_PATH) -> set[str]:
    """Scopes recorded in a saved token file (empty if unreadable)."""
    try:
        scopes = json.loads(path.read_text()).get("scopes") or []
    except Exception:
        return set()
    if isinstance(scopes, str):
        scopes = scopes.split()
    return set(scopes)


def token_has_excess_scopes(path: Path = TOKEN_PATH) -> bool:
    """True when a saved token grants more than JARVIS now requests."""
    return path.exists() and bool(granted_scopes(path) - set(SCOPES))


def revoke_and_remove_token(path: Path = TOKEN_PATH) -> bool:
    """Revoke the saved token with Google, then delete it. Returns True if Google confirmed."""
    if not path.exists():
        return False
    revoked = False
    try:
        data = json.loads(path.read_text())
        token = data.get("refresh_token") or data.get("token")
        if token:
            body = urllib.parse.urlencode({"token": token}).encode()
            req = urllib.request.Request(
                _REVOKE_URL, data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                revoked = resp.status == 200
    except Exception:
        revoked = False
    path.unlink(missing_ok=True)
    return revoked


def _save_token(creds) -> None:
    TOKEN_PATH.write_text(creds.to_json())
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass


def get_credentials():
    """
    Return valid Google credentials.
    Opens browser for OAuth on first run, refreshes token automatically after.
    Raises FileNotFoundError if google_credentials.json is missing.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "Google auth libraries not installed. Run: "
            "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )

    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            f"Google credentials not found at {CREDS_PATH}.\n"
            "Steps to fix:\n"
            "  1. Go to console.cloud.google.com\n"
            "  2. Create a project → Enable Gmail API + Google Calendar API\n"
            "  3. Credentials → Create OAuth 2.0 Client ID (Desktop app)\n"
            "  4. Download JSON → save as data/google_credentials.json\n"
            "  Then say 'connect Google' to complete setup."
        )

    if token_has_excess_scopes():
        raise PermissionError(
            "Google is still connected with the old, broader permissions. "
            "Run `python setup_google.py` to revoke them and reconnect with read-only Gmail, "
            "send-only mail, and events-only Calendar."
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        _save_token(creds)

    return creds


def get_service(api: str, version: str):
    """Build and return a Google API service client."""
    from googleapiclient.discovery import build
    return build(api, version, credentials=get_credentials())
