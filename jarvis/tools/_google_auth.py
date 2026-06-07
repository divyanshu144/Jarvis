"""
Shared Google OAuth helper.
Credentials JSON downloaded from Google Cloud Console → data/google_credentials.json
Token auto-saved to data/google_token.json after first browser auth.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
CREDS_PATH = _ROOT / "data" / "google_credentials.json"
TOKEN_PATH = _ROOT / "data" / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts.readonly",
]


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

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def get_service(api: str, version: str):
    """Build and return a Google API service client."""
    from googleapiclient.discovery import build
    return build(api, version, credentials=get_credentials())
