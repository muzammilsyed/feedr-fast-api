"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "Pixer API"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://pixer_user:pixer_password@localhost:5432/pixer_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "2rt2UV4drlLb_s_a92hOjZPa-LwiVT4Zzfe01WuyvWE"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Local file storage (upload dir relative to backend root)
    UPLOAD_DIR: str = "uploads"
    MEDIA_BASE_URL: str = "http://frbackend.ddns.net"

    # File storage (MinIO/S3) - for future bucket switch
    S3_ENDPOINT_URL: str | None = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_MEDIA: str = "pixer-media"
    S3_BUCKET_VIDEOS: str = "pixer-videos"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"


settings = Settings()
