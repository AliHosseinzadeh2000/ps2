"""Configuration management using Pydantic settings."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class ExchangeConfig(BaseSettings):
    """Configuration for a single exchange."""

    api_key: str = Field(default="", env="EXCHANGE_API_KEY")
    api_secret: str = Field(default="", env="EXCHANGE_API_SECRET")
    base_url: str = Field(default="", env="EXCHANGE_BASE_URL")
    maker_fee: float = Field(default=0.001, ge=0.0, le=1.0)
    taker_fee: float = Field(default=0.001, ge=0.0, le=1.0)
    timeout: int = Field(default=30, ge=1)

    class Config:
        """Pydantic config."""

        env_prefix = ""
        case_sensitive = False


class NobitexConfig(ExchangeConfig):
    """Nobitex exchange configuration."""

    api_key: str = Field(default="", env="NOBITEX_API_KEY")
    api_secret: str = Field(default="", env="NOBITEX_API_SECRET")
    base_url: str = Field(default="https://api.nobitex.ir", env="NOBITEX_BASE_URL")
    maker_fee: float = Field(default=0.0005)
    taker_fee: float = Field(default=0.001)


class WallexConfig(ExchangeConfig):
    """Wallex exchange configuration."""

    api_key: str = Field(default="", env="WALLEX_API_KEY")
    api_secret: str = Field(default="", env="WALLEX_API_SECRET")
    base_url: str = Field(default="https://api.wallex.ir", env="WALLEX_BASE_URL")
    maker_fee: float = Field(default=0.0005)
    taker_fee: float = Field(default=0.001)


class TradingConfig(BaseSettings):
    """Trading strategy configuration."""

    min_spread_percent: float = Field(default=0.5, ge=0.0)
    min_profit_usdt: float = Field(default=1.0, ge=0.0)
    max_position_size_usdt: float = Field(default=1000.0, ge=0.0)
    order_timeout_seconds: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0.0)
    polling_interval_seconds: float = Field(default=1.0, ge=0.1)

    class Config:
        """Pydantic config."""

        env_prefix = "TRADING_"
        case_sensitive = False


class AIConfig(BaseSettings):
    """AI/ML model configuration."""

    model_path: str = Field(default="./models/xgboost_model.pkl", env="AI_MODEL_PATH")
    training_data_path: str = Field(
        default="./data/training_data.csv", env="AI_TRAINING_DATA_PATH"
    )
    feature_count: int = Field(default=20, ge=1)
    prediction_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    class Config:
        """Pydantic config."""

        env_prefix = "AI_"
        case_sensitive = False


class APIConfig(BaseSettings):
    """FastAPI application configuration."""

    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, ge=1, le=65535, env="API_PORT")
    debug: bool = Field(default=False, env="API_DEBUG")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    class Config:
        """Pydantic config."""

        env_prefix = "API_"
        case_sensitive = False


class Settings(BaseSettings):
    """Main application settings."""

    nobitex: NobitexConfig = Field(default_factory=NobitexConfig)
    wallex: WallexConfig = Field(default_factory=WallexConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

