#!/usr/bin/env python3
"""
Google OAuth setup for JARVIS.

Run this once to connect Gmail and Google Calendar:
    python setup_google.py

You need a Google Cloud project with the Gmail and Calendar APIs enabled.
Download the OAuth credentials JSON and place it at data/google_credentials.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CREDS_PATH = DATA_DIR / "google_credentials.json"
TOKEN_PATH = DATA_DIR / "google_token.json"


def main() -> None:
    print("\n━━━ JARVIS — Google Setup ━━━\n")

    # Step 1: Check credentials file
    if not CREDS_PATH.exists():
        print("Step 1: Download OAuth credentials from Google Cloud Console")
        print()
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project (or select an existing one)")
        print("  3. Enable these APIs:")
        print("     • Gmail API")
        print("     • Google Calendar API")
        print("     • People API (for Contacts)")
        print("  4. Go to APIs & Services → Credentials")
        print("  5. Create OAuth 2.0 Client ID → Desktop app")
        print("  6. Download the JSON file")
        print(f"  7. Save it to: {CREDS_PATH}")
        print()
        print("Then run this script again.")
        sys.exit(0)

    print(f"✓ Found credentials at {CREDS_PATH}")

    # Step 2: Run OAuth flow
    print("\nStep 2: Authorising with Google (browser will open)...")
    print()

    try:
        from jarvis.tools._google_auth import get_credentials
        creds = get_credentials()
        print("✓ Authentication successful!")
        print(f"✓ Token saved to {TOKEN_PATH}")
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install Google API libraries:")
        print("  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # Step 3: Verify access
    print("\nStep 3: Testing access...")

    try:
        from jarvis.tools._google_auth import get_service

        # Test Gmail
        gmail_service = get_service("gmail", "v1")
        profile = gmail_service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "unknown")
        print(f"✓ Gmail: connected as {email}")

        # Test Calendar
        cal_service = get_service("calendar", "v3")
        cal_list = cal_service.calendarList().list(maxResults=1).execute()
        cals = cal_list.get("items", [])
        cal_name = cals[0].get("summary", "primary") if cals else "primary"
        print(f"✓ Calendar: connected ({cal_name})")

    except Exception as e:
        print(f"Verification error: {e}")
        print("Auth token saved — JARVIS may still work. Try running jarvis.py.")

    print()
    print("━━━ Setup complete! ━━━")
    print()
    print("JARVIS can now:")
    print("  • Read and send Gmail")
    print("  • View and create calendar events")
    print("  • Announce upcoming meetings proactively")
    print("  • Alert you to new urgent emails")
    print()
    print("Start JARVIS: python jarvis.py")


if __name__ == "__main__":
    main()
