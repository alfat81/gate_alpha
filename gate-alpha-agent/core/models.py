"""Pydantic model for LLM analysis validation."""

from pydantic import BaseModel, Field, field_validator


class LLMAnalysisModel(BaseModel):
    """Schema for LLM trading analysis response."""

    must_trade: bool = Field(..., description="Whether to trade this ticker")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level (0.0-1.0)")
    reason: str = Field(..., description="Explanation of the decision")
    entry_price: float = Field(..., gt=0.0, description="Suggested entry price")
    stop_loss: float = Field(..., gt=0.0, description="Suggested stop loss price")
    take_profit_levels: list[float] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="Take profit price levels"
    )
    risk_score: int = Field(..., ge=1, le=10, description="Risk assessment score (1-10)")
    position_size_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Position size as percentage of portfolio"
    )

    @field_validator("take_profit_levels")
    @classmethod
    def validate_tp_levels(cls, v: list[float]) -> list[float]:
        """Validate take profit levels are positive and sorted."""
        if not all(x > 0 for x in v):
            raise ValueError("All take profit levels must be positive")
        return v
