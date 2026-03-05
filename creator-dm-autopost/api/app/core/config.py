from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "creator-dm-autopost-api"
    app_env: str = "local"
    app_port: int = 8000

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "creator_dm"
    postgres_user: str = "creator"
    postgres_password: str = "creator"

    redis_host: str = "localhost"
    redis_port: int = 6379

    discord_bot_token: str = ""
    discord_guild_id: str = ""
    discord_api_base_url: str = "https://discord.com/api/v10"
    discord_dm_dry_run: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
