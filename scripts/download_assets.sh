#!/bin/bash
# Script to download Font Awesome 6.4.0 assets locally

BASE_URL="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0"
TARGET_CSS="static/vendor/fontawesome/css"
TARGET_FONTS="static/vendor/fontawesome/webfonts"

echo "Downloading CSS..."
curl -sL "$BASE_URL/css/all.min.css" -o "$TARGET_CSS/all.min.css"

echo "Downloading Webfonts..."
# List of fonts usually needed
FONTS=(
  "fa-brands-400.woff2"
  "fa-regular-400.woff2"
  "fa-solid-900.woff2"
  "fa-v4compatibility.woff2"
)

for font in "${FONTS[@]}"; do
  echo "Downloading $font..."
  curl -sL "$BASE_URL/webfonts/$font" -o "$TARGET_FONTS/$font"
done

echo "Download complete."
ls -R static/vendor/fontawesome
