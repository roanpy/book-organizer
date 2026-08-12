#!/bin/bash

API_BASE="http://localhost:18000/api"
CONFIG_FILE="${BOOK_ORGANIZER_CONFIG_FILE:-$HOME/.book_organizer/book_organizer_config.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file not found: $CONFIG_FILE"
    exit 1
fi

echo "Testing Offline Batch Enhance..."
# Get a sample filename from target_dir
TARGET_DIR=$("$PYTHON_BIN" -c "import json; print(json.load(open('$CONFIG_FILE')).get('target_dir'))" 2>/dev/null)
if [ -z "$TARGET_DIR" ]; then
    echo "Target directory not found in config."
else
    SAMPLE_FILE=$(ls "$TARGET_DIR" | grep -E ".epub|.pdf" | head -n 1)
    if [ -z "$SAMPLE_FILE" ]; then
        echo "No sample files found in $TARGET_DIR"
    else
        echo "Sample file: $SAMPLE_FILE"
        curl -s -X POST "$API_BASE/batch_enhance_single" \
             -H "Content-Type: application/json" \
             -d "{\"filename\": \"$SAMPLE_FILE\", \"engine\": \"offline\"}" | "$PYTHON_BIN" -m json.tool
    fi
fi

echo -e "\nTesting Offline Batch Organize..."
# Get a sample filename from source_dir
SOURCE_DIR=$("$PYTHON_BIN" -c "import json; print(json.load(open('$CONFIG_FILE')).get('source_dir'))" 2>/dev/null)
if [ -z "$SOURCE_DIR" ]; then
    echo "Source directory not found in config."
else
    SAMPLE_SOURCE_FILE=$(ls "$SOURCE_DIR" | grep -E ".epub|.pdf" | head -n 1)
    if [ -z "$SAMPLE_SOURCE_FILE" ]; then
        echo "No sample source files found in $SOURCE_DIR"
    else
        echo "Sample source file: $SAMPLE_SOURCE_FILE"
        curl -s -X POST "$API_BASE/batch_organize_single" \
             -H "Content-Type: application/json" \
             -d "{\"filename\": \"$SAMPLE_SOURCE_FILE\", \"engine\": \"offline\", \"enable_enhanced_summary\": true, \"enable_online_search\": false}" | "$PYTHON_BIN" -m json.tool
fi
fi
