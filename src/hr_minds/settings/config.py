"""
Configuration Module for HR Minds API.

This module uses python-dotenv to interpolate environment variables in .env
and Pydantic's BaseSettings to load and validate them.
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load and interpolate .env variables (e.g. ${POSTGRES_PASSWORD})
load_dotenv(override=True)


class Settings(BaseSettings):
    """
    Application Settings schema.
    """

    # --- App Configuration & Metadata ---
    PROJECT_NAME: str = "HR Minds API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for employee and HR Management with Agentic RAG"
    DEBUG: bool = False
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"

    # --- Database ---
    DATABASE_URL: str

    # --- Security & Auth Configuration ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- AWS S3 (Media & Resume Uploads) ---
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_S3_BUCKET_NAME: str | None = None
    AWS_REGION: str = "us-east-1"

    # --- AI & Agentic RAG Configuration ---
    # Any OpenAI-compatible chat endpoint (OmniRoute, Ollama, Gemini's compatibility URL).
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    # One model per capability on that endpoint. LLM_MODEL is the default (chat agent);
    # REASONING (screening) and FAST (bulk extraction) fall back to it when unset.
    LLM_MODEL: str | None = None
    LLM_MODEL_FAST: str | None = None
    LLM_MODEL_REASONING: str | None = None
    QDRANT_URL: str = "http://localhost:6333"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton instance imported across the application
settings = Settings()
