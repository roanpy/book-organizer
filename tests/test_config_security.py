import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from book_organizer.routers import config as config_router


def test_public_config_redacts_api_keys():
    public_config = config_router._public_config(
        {
            "gemini": {"api_key": "example-gemini-secret", "model_name": "gemini"},
            "deepseek": {"api_key": "example-deepseek-secret", "model_name": "chat"},
            "ollama": {"url": "http://127.0.0.1:11434"},
            "custom_providers": {
                "demo": {"api_key": "custom-secret-value", "model_name": "demo"}
            },
        }
    )

    assert "api_key" not in public_config["gemini"]
    assert "api_key" not in public_config["deepseek"]
    assert "api_key" not in public_config["custom_providers"]["demo"]
    assert public_config["gemini"]["configured"] is True
    assert public_config["custom_providers"]["demo"]["configured"] is True
    assert "api_key_masked" in public_config["gemini"]


def test_merge_secret_config_preserves_existing_key_for_blank_or_masked_input():
    existing = {"api_key": "existing-key", "model_name": "old"}

    blank_merged = config_router._merge_secret_config(
        existing, {"api_key": "", "model_name": "new"}
    )
    masked_merged = config_router._merge_secret_config(
        existing, {"api_key": "exis...-key", "model_name": "newer"}
    )

    assert blank_merged["api_key"] == "existing-key"
    assert blank_merged["model_name"] == "new"
    assert masked_merged["api_key"] == "existing-key"
    assert masked_merged["model_name"] == "newer"


def test_merge_secret_config_allows_explicit_clear():
    merged = config_router._merge_secret_config(
        {"api_key": "existing-key", "model_name": "old"},
        {"api_key": "", "model_name": ""},
    )

    assert merged["api_key"] == ""
    assert merged["model_name"] == ""
