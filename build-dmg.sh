#!/bin/bash

# exit on error
set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
NAME="BatteryUsage"
APP="${NAME}.app"
BUILD="${SCRIPT_DIR}/build"
DIST="${SCRIPT_DIR}/dist"
DMG_DIR="${SCRIPT_DIR}/dist-dmg"
DMG="${DMG_DIR}/${NAME}.dmg"

rm -fr "${BUILD}"
rm -fr "${DIST}"
rm -fr "${DMG_DIR}"
mkdir -p "${DMG_DIR}"

. ${SCRIPT_DIR}/venv/bin/activate

python3 setup.py py2app

create-dmg \
  --volicon src/mac_battery_usage/application.icns \
  --volname "${NAME} Installer" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "${APP}" 200 190 \
  --hide-extension "${APP}" \
  --app-drop-link 600 185 \
  "${DMG}" "${DIST}"
