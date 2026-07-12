#!/bin/bash
# Simple wrapper to test OLED screens on Mac

SCREEN="${1:-waiting}"

source macos_venv/bin/activate
export PYTHONPATH="/Users/robert/src/axehead_fm/src:$PYTHONPATH"
python3 screen_tester.py "$SCREEN"
