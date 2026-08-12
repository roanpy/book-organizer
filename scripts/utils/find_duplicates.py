
import json
import os
import re
from pathlib import Path

TARGET_DIR = os.environ.get("BOOK_ORGANIZER_TARGET_DIR", str(Path.home() / "Books"))

def normalize_title(filename):
    # Remove extension
    name = os.path.splitext(filename)[0]

    # Split by colon (half or full width)
    # The user said "Before : including full/half width"
    # Regex to find the first colon
    match = re.search(r'[:：]', name)
    if match:
        extracted = name[:match.start()]
    else:
        extracted = name

    return extracted.strip()

def find_duplicates():
    if not os.path.exists(TARGET_DIR):
        print(json.dumps({"error": f"Directory not found: {TARGET_DIR}"}))
        return

    groups = {}

    for root, dirs, files in os.walk(TARGET_DIR):
        for file in files:
            if file.lower().endswith('.epub'):
                # Extract title
                title = normalize_title(file)

                if title not in groups:
                    groups[title] = []

                # Store full path and filename for context
                groups[title].append({
                    "path": os.path.join(root, file),
                    "filename": file
                })

    # Filter for duplicates (more than 1)
    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    print(json.dumps(duplicates, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    find_duplicates()
