from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TisTru"
    use_local_llm: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    tavily_api_key: str | None = None
    request_timeout_seconds: int = 20
    frontend_origin: str = "http://localhost:3000"
    firebase_credentials_path: str | None = None
    firebase_service_account_json: str | None = None
    admin_path_secret: str | None = None
    admin_emails: str = ""
    trust_x_forwarded_for: bool = False
    fact_check_rate_limit: int = 5
    fact_check_rate_window_seconds: int = 60
    fact_check_anon_limit: int = 1
    fact_check_user_daily_limit: int = 5
    max_text_chars: int = 8000
    min_text_chars: int = 20
    max_url_length: int = 2048
    max_image_bytes: int = 5 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
