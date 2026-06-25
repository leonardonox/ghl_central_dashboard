from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    app_name: str = 'Future GHL Central Dashboard'
    environment: str = 'dev'
    database_url: str
    secret_key: str
    token_encryption_key: str
    ghl_base_url: str = 'https://services.leadconnectorhq.com'
    ghl_api_version: str = '2021-07-28'
    sync_interval_minutes: int = 5
    dashboard_username: str = 'admin'
    dashboard_password: str = 'admin123'
    render_deploy_hook_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
