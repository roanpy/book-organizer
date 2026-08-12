#!/bin/bash
# Script to download Font Awesome 6.4.0 assets locally

set -euo pipefail

BASE_URL="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0"
TARGET_CSS="static/vendor/fontawesome/css"
TARGET_FONTS="static/vendor/fontawesome/webfonts"

download_verified() {
  local url="$1"
  local destination="$2"
  local expected_sha256="$3"
  local temporary="${destination}.download"

  curl -fsSL "$url" -o "$temporary"
  echo "$expected_sha256  $temporary" | shasum -a 256 -c - >/dev/null
  mv "$temporary" "$destination"
}

echo "Downloading CSS..."
download_verified \
  "$BASE_URL/css/all.min.css" \
  "$TARGET_CSS/all.min.css" \
  "1edb1725a9ea8ca4dcf2f5508cee183218aa1685e47c1b23056717f754f58ebf"

echo "Downloading Webfonts..."
# List of fonts usually needed
FONTS=(
  "fa-brands-400.woff2"
  "fa-regular-400.woff2"
  "fa-solid-900.woff2"
  "fa-v4compatibility.woff2"
)

for font in "${FONTS[@]}"; do
  case "$font" in
    fa-brands-400.woff2) sha256="748332090c4b8e20f95d0ff59f0be20fa9c889359d3b36d4b886d73376054207" ;;
    fa-regular-400.woff2) sha256="8e7e5ea1b15f62ab14dbd41768e8fbcd21cc859a4ea5da812457ee714299fb35" ;;
    fa-solid-900.woff2) sha256="7152a6933ee3d690ec2af3d09da9d701723d16aa3410a6d80f28ff8866f3b880" ;;
    fa-v4compatibility.woff2) sha256="694a17c3d9d6c05f8aac63c544615552a4b220e9a4de863d87341a6bcfc1bc8d" ;;
  esac
  echo "Downloading $font..."
  download_verified \
    "$BASE_URL/webfonts/$font" \
    "$TARGET_FONTS/$font" \
    "$sha256"
done

echo "Download complete."
ls -R static/vendor/fontawesome
