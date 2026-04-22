"""Configuration settings for Gate Alpha Agent."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class GateConfig(BaseSettings):
    """Gate.io API configuration."""

    api_key: str = Field(default="", description="Gate.io API key")
    api_secret: str = Field(default="", description="Gate.io API secret")
    base_url: str = Field(
        default="https://fx-api-testnet.gateio.ws/api/v4",
        description="Gate.io API base URL (testnet)"
    )

    class Config:
        env_prefix = "GATE_"
        env_file = ".env"


class LLMConfig(BaseSettings):
    """LLM/Ollama configuration."""

    host: str = Field(default="http://localhost:11434", description="Ollama host URL")
    model: str = Field(default="qwen2.5:7b", description="Ollama model name")
    temperature: float = Field(default=0.15, ge=0.0, le=1.0, description="LLM temperature")
    max_retries: int = Field(default=3, ge=1, description="Max retry attempts")

    class Config:
        env_prefix = "OLLAMA_"
        env_file = ".env"


class TradingConfig(BaseSettings):
    """Trading configuration."""

    max_position_pct: float = Field(default=3.0, gt=0.0, le=100.0, description="Max position as % of portfolio")
    stop_loss_pct: float = Field(default=5.0, gt=0.0, le=100.0, description="Stop loss percentage")
    max_risk_score: int = Field(default=8, ge=1, le=10, description="Maximum risk score allowed")
    max_daily_loss_pct: float = Field(default=15.0, gt=0.0, le=100.0, description="Max daily loss percentage")
    scan_interval_seconds: int = Field(default=300, ge=60, description="Scan interval in seconds")

    # Scanner settings
    min_volume_usd: float = Field(default=100000.0, gt=0.0, description="Minimum 24h volume in USD")
    max_volume_usd: float = Field(default=5000000.0, gt=0.0, description="Maximum 24h volume in USD")
    min_change_24h_pct: float = Field(default=15.0, gt=0.0, description="Minimum |24h change| percentage")
    max_spread_pct: float = Field(default=2.0, gt=0.0, le=100.0, description="Maximum bid-ask spread percentage")
    top_n_tickers: int = Field(default=10, ge=1, description="Number of top tickers to return")

    class Config:
        env_file = ".env"


class Settings(BaseModel):
    """Main settings container."""

    gate: GateConfig = Field(default_factory=GateConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            gate=GateConfig(),
            llm=LLMConfig(),
            trading=TradingConfig()
        )
