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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
