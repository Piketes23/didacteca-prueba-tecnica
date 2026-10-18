from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    provided_service_base_url: str = "https://temp.didacteca.site"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    context_timeout_seconds: float = 10.0
    llm_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()