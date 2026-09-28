#!/usr/bin/env bash
# Build the Carrom desktop app on macOS or Linux.
#   ./build.sh            -> dist/Carrom.app (macOS) or dist/Carrom (Linux)
#   ./build.sh --dmg      -> also produces dist/Carrom-macOS.dmg
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
"$PYTHON" -c "import tkinter" || {
  echo "Tk is missing. macOS: install python.org Python or 'brew install python-tk'." >&2
  echo "Ubuntu/Debian: sudo apt install python3-tk" >&2
  exit 1
}

"$PYTHON" -m pip install --upgrade --quiet pyinstaller
rm -rf build dist
"$PYTHON" -m PyInstaller --noconfirm --clean carrom.spec

if [[ "$(uname -s)" == "Darwin" ]]; then
  # Ad-hoc signature so Gatekeeper lets a locally built app run.
  codesign --force --deep --sign - dist/Carrom.app
  echo "Built dist/Carrom.app"
  if [[ "${1:-}" == "--dmg" ]]; then
    hdiutil create -volname Carrom -srcfolder dist/Carrom.app -ov -format UDZO dist/Carrom-macOS.dmg
    echo "Built dist/Carrom-macOS.dmg"
  fi
else
  echo "Built dist/Carrom"
fi
