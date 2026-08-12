from book_organizer.ai_engines.dispatcher import build_litellm_model_options


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
