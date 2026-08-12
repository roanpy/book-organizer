import os
import subprocess
import sys
from pathlib import Path

from book_organizer.ai_engines.dispatcher import (
    build_litellm_model_options,
    format_ai_error,
)


def test_litellm_uses_bundled_model_map_by_default():
    env = os.environ.copy()
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    src_dir = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (src_dir, env.get("PYTHONPATH")) if part
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import book_organizer.ai_engines.dispatcher; "
            "assert os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] == 'True'",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_ai_errors_are_actionable_and_do_not_leak_provider_payloads():
    raw = 'ServiceUnavailableError: 503 {"internal": "provider payload"}'
    message = format_ai_error(raw)
    assert message == "AI 服务暂时繁忙（503），请稍后重试或切换其他模型。"
    assert "provider payload" not in message


def test_missing_provider_has_specific_configuration_message():
    message = format_ai_error("LLM Provider NOT provided. model=deepseek-v4-flash")
    assert "Provider" in message
    assert "deepseek-v4-flash" not in message


def test_litellm_options_prefixes_custom_provider_model():
    options = build_litellm_model_options(
        "my_openrouter",
        {
            "type": "openrouter",
            "model_name": "deepseek/deepseek-chat-v3-0324",
            "api_key": "key",
            "base_url": "https://openrouter.ai/api/v1",
        },
    )

    assert options["model"] == "openrouter/deepseek/deepseek-chat-v3-0324"
    assert options["api_base"] == "https://openrouter.ai/api/v1"


def test_litellm_options_prefixes_unqualified_custom_model():
    options = build_litellm_model_options(
        "my_openrouter",
        {
            "type": "openrouter",
            "model_name": "deepseek-v4-flash",
            "api_key": "key",
            "base_url": "https://openrouter.ai/api/v1",
        },
    )

    assert options["model"] == "openrouter/deepseek-v4-flash"


def test_litellm_options_treats_custom_base_url_as_openai_compatible():
    options = build_litellm_model_options(
        "local_proxy",
        {
            "type": "custom",
            "model_name": "deepseek-v4-flash",
            "api_key": "key",
            "base_url": "https://example.test/v1",
        },
    )

    assert options["model"] == "openai/deepseek-v4-flash"
