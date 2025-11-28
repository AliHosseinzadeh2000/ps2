"""Configuration management using Pydantic settings."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file into environment before creating any settings
# This ensures nested BaseSettings can access the env vars
# Use override=False to respect existing environment variables
env_path = Path(".env")
if env_path.exists():
    load_dotenv(env_path, override=False)


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
        extra = "ignore"  # Ignore extra fields from .env file


class NobitexConfig(ExchangeConfig):
    """Nobitex exchange configuration."""

    # Nobitex uses token-based authentication (obtained via login)
    # You can provide either username/password OR token directly
    username: str = Field(default="", env="NOBITEX_USERNAME")
    password: str = Field(default="", env="NOBITEX_PASSWORD")
    token: str = Field(default="", env="NOBITEX_TOKEN")  # Direct token (if you have it)
    api_key: str = Field(default="", env="NOBITEX_API_KEY")  # Legacy/experimental API key
    api_secret: str = Field(default="", env="NOBITEX_API_SECRET")  # Legacy/experimental API secret
    base_url: str = Field(default="https://apiv2.nobitex.ir", env="NOBITEX_BASE_URL")
    maker_fee: float = Field(default=0.0005)
    taker_fee: float = Field(default=0.001)

    class Config:
        """Pydantic config."""

        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


class WallexConfig(ExchangeConfig):
    """Wallex exchange configuration."""

    api_key: str = Field(default="", env="WALLEX_API_KEY")
    api_secret: str = Field(default="", env="WALLEX_API_SECRET")
    base_url: str = Field(default="https://api.wallex.ir", env="WALLEX_BASE_URL")
    maker_fee: float = Field(default=0.0005)
    taker_fee: float = Field(default=0.001)

    class Config:
        """Pydantic config."""

        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


class KucoinConfig(ExchangeConfig):
    """KuCoin exchange configuration."""

    api_key: str = Field(default="", env="KUCOIN_API_KEY")
    api_secret: str = Field(default="", env="KUCOIN_API_SECRET")
    api_passphrase: str = Field(default="", env="KUCOIN_API_PASSPHRASE")
    base_url: str = Field(default="https://api.kucoin.com", env="KUCOIN_BASE_URL")
    maker_fee: float = Field(default=0.001)
    taker_fee: float = Field(default=0.001)

    class Config:
        """Pydantic config."""

        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


class InvexConfig(ExchangeConfig):
    """Invex exchange configuration."""

    api_key: str = Field(default="", env="INVEX_API_KEY")
    api_secret: str = Field(default="", env="INVEX_API_SECRET")
    base_url: str = Field(default="https://api.invex.ir/trading/v1", env="INVEX_BASE_URL")
    maker_fee: float = Field(default=0.0005)
    taker_fee: float = Field(default=0.001)

    class Config:
        """Pydantic config."""

        # Read from environment variables (populated by load_dotenv above)
        # BaseSettings reads from os.environ by default when env_file is not specified
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


class TabdealConfig(ExchangeConfig):
    """Tabdeal exchange configuration."""

    api_key: str = Field(default="", env="TABDEAL_API_KEY")
    api_secret: str = Field(default="", env="TABDEAL_API_SECRET")
    base_url: str = Field(default="https://api.tabdeal.org", env="TABDEAL_BASE_URL")
    maker_fee: float = Field(default=0.0005)
    taker_fee: float = Field(default=0.001)

    class Config:
        """Pydantic config."""

        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


class TradingConfig(BaseSettings):
    """Trading strategy configuration."""

    min_spread_percent: float = Field(default=0.5, ge=0.0)
    min_profit_usdt: float = Field(default=1.0, ge=0.0)
    max_position_size_usdt: float = Field(default=1000.0, ge=0.0)
    order_timeout_seconds: int = Field(default=30, ge=1)
    polling_interval_seconds: float = Field(default=1.0, ge=0.1)
    default_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0.0)
    # Risk management
    max_position_per_exchange: float = Field(default=5000.0, ge=0.0)
    daily_loss_limit: float = Field(default=100.0, ge=0.0)
    max_slippage_percent: float = Field(default=0.5, ge=0.0, le=10.0)
    require_balance_check: bool = Field(default=True)

    class Config:
        """Pydantic config."""

        env_prefix = "TRADING_"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file


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
    kucoin: KucoinConfig = Field(default_factory=KucoinConfig)
    invex: InvexConfig = Field(default_factory=InvexConfig)
    tabdeal: TabdealConfig = Field(default_factory=TabdealConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    log_level: str = Field(default="DEBUG", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env file that don't match model fields


# Global settings instance
# Note: We load .env at module level (above) using load_dotenv to populate os.environ.
# However, BaseSettings doesn't automatically read from os.environ when using Field(env=...).
# We need to manually pass environment variables or use _env_file parameter.
# Since nested BaseSettings don't work well with .env files (they see all vars),
# we manually extract only the needed env vars and pass them.
import os as _os

def _get_env_or_default(key: str, default: str = "") -> str:
    """Get environment variable or return default."""
    return _os.getenv(key, default)

_settings_temp = Settings()
settings = Settings(
    nobitex=NobitexConfig(
        username=_get_env_or_default("NOBITEX_USERNAME"),
        password=_get_env_or_default("NOBITEX_PASSWORD"),
        token=_get_env_or_default("NOBITEX_TOKEN"),
        api_key=_get_env_or_default("NOBITEX_API_KEY"),
        api_secret=_get_env_or_default("NOBITEX_API_SECRET"),
    ),
    wallex=WallexConfig(
        api_key=_get_env_or_default("WALLEX_API_KEY"),
        api_secret=_get_env_or_default("WALLEX_API_SECRET"),
    ),
    kucoin=KucoinConfig(
        api_key=_get_env_or_default("KUCOIN_API_KEY"),
        api_secret=_get_env_or_default("KUCOIN_API_SECRET"),
        api_passphrase=_get_env_or_default("KUCOIN_API_PASSPHRASE"),
    ),
    invex=InvexConfig(
        api_key=_get_env_or_default("INVEX_API_KEY"),
        api_secret=_get_env_or_default("INVEX_API_SECRET"),
    ),
    tabdeal=TabdealConfig(
        api_key=_get_env_or_default("TABDEAL_API_KEY"),
        api_secret=_get_env_or_default("TABDEAL_API_SECRET"),
    ),
    trading=TradingConfig(),
    ai=AIConfig(),
    api=APIConfig(),
    log_level=_settings_temp.log_level,
    environment=_settings_temp.environment,
)

