#!/usr/bin/env bash
# JARVIS launcher — sets Qt plugin path for Anaconda Python
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

QT_PLUGIN_PATH=/opt/anaconda3/lib/python3.13/site-packages/PyQt6/Qt6/plugins \
QT_QPA_PLATFORM_PLUGIN_PATH=/opt/anaconda3/lib/python3.13/site-packages/PyQt6/Qt6/plugins/platforms \
    python3 jarvis.py "$@"
