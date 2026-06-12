import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Invoice & Bank Statement Parsing API"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/parser_db")
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: set = {"pdf", "csv"}
    PARSER_PREFIX:str = "/api/v1"

    class Config:
        env_file = ".env"

settings = Settings()