from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    PROJECT_NAME: str = "API agrotecnio"
    DATABASE_URL: str = "sqlite:////data/logistics.db"


settings = Settings()