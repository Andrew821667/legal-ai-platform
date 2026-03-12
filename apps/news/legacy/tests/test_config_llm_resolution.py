from app.config import Settings


def test_resolve_deepseek_from_openai_compatible_env() -> None:
    settings = Settings(
        openai_api_key="sk-test",
        openai_base_url="https://api.deepseek.com/v1",
        news_model="deepseek-chat",
        deepseek_api_key="",
        deepseek_model="deepseek-chat",
    )

    assert settings.uses_deepseek_via_openai_base is True
    assert settings.resolved_deepseek_api_key == "sk-test"
    assert settings.resolved_deepseek_base_url == "https://api.deepseek.com/v1"
    assert settings.resolved_deepseek_model == "deepseek-chat"
    assert settings.resolved_openai_model_analysis == "deepseek-chat"
