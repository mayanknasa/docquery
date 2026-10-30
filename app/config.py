from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (12 factor style)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "docquery"
    api_key: str | None = None  # if set, every /documents call needs X-API-Key

    storage_backend: str = "local"  # local | aws
    llm_provider: str = "mock"  # mock | openai

    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"

    aws_region: str = "us-east-1"
    s3_bucket: str = ""
    dynamodb_table: str = ""

    chunk_size: int = 800
    chunk_overlap: int = 100
    embed_batch_size: int = 32
    max_concurrency: int = 4
    max_upload_mb: int = 5
    top_k: int = 4
