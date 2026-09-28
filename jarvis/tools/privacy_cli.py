"""Operator CLI for user data rights and privacy housekeeping.

Usage:
    python3 -m jarvis.tools.privacy_cli export
    python3 -m jarvis.tools.privacy_cli forget --yes
    python3 -m jarvis.tools.privacy_cli redact-existing

The same export/forget actions are available by voice: "export my data", "forget everything".
"""

from __future__ import annotations

import argparse
import json
import sys

from jarvis.core import privacy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="privacy_cli", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export", help="Write all stored user data to data/exports/*.json")
    forget = sub.add_parser("forget", help="Delete conversation memory, profile, traces and logs")
    forget.add_argument("--yes", action="store_true", help="Confirm the irreversible delete")
    sub.add_parser("redact-existing", help="Redact rows, embeddings and logs written before redaction existed")
    args = parser.parse_args(argv)

    if args.command == "export":
        print(f"Exported to {privacy.export_user_data()}")
        return 0
    if args.command == "forget":
        if not args.yes:
            print("Refusing to delete without --yes. This cannot be undone.")
            return 2
        print(json.dumps(privacy.forget_user_data(), indent=2))
        return 0
    if args.command == "redact-existing":
        print(json.dumps(privacy.redact_existing_data(), indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
