import json
import os

import requests

API_BASE = "http://localhost:8000/api"

def test_offline_batch_enhance():
    print("Testing Offline Batch Enhance...")
    # Find a sample file in target_dir
    config = requests.get(f"{API_BASE}/config").json()
    target_dir = config.get("target_dir")

    if not target_dir:
        print("Target directory not set, skipping test.")
        return

    files = [f for f in os.listdir(target_dir) if f.endswith('.epub') or f.endswith('.pdf')]
    if not files:
        print("No sample files found in target directory, skipping test.")
        return

    sample_file = files[0]
    payload = {
        "filename": sample_file,
        "engine": "offline"
    }

    response = requests.post(f"{API_BASE}/batch_enhance_single", json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Result (Metadata): {json.dumps(result.get('metadata'), ensure_ascii=False, indent=2)}")
        print(f"Result (Warning): {result.get('warning')}")
        assert "metadata" in result
        assert "summary" in result
        assert result["summary"] == ""
    else:
        print(f"Error: {response.text}")

def test_offline_batch_organize():
    print("\nTesting Offline Batch Organize...")
    config = requests.get(f"{API_BASE}/config").json()
    source_dir = config.get("source_dir")

    if not source_dir:
        print("Source directory not set, skipping test.")
        return

    files = [f for f in os.listdir(source_dir) if f.endswith('.epub') or f.endswith('.pdf')]
    if not files:
        print("No sample files found in source directory, skipping test.")
        return

    sample_file = files[0]
    payload = {
        "filename": sample_file,
        "engine": "offline",
        "enable_enhanced_summary": True,
        "enable_online_search": False
    }

    response = requests.post(f"{API_BASE}/batch_organize_single", json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Result (Metadata): {json.dumps(result.get('metadata'), ensure_ascii=False, indent=2)}")
        print(f"Result (Suggestions): {result.get('suggestions')}")
        print(f"Result (Category): {result.get('category')}")
        print(f"Result (Warning): {result.get('warning')}")
        assert "metadata" in result
        assert "suggestions" in result
        assert "category" in result
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    try:
        test_offline_batch_enhance()
        test_offline_batch_organize()
    except Exception as e:
        print(f"Test failed: {e}")
