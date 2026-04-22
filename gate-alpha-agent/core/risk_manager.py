"""Risk manager for validating trading decisions."""

from dataclasses import dataclass
from typing import NamedTuple

import structlog

from config.settings import TradingConfig

logger = structlog.get_logger(__name__)


@dataclass
class RiskValidationResult:
    """Result of risk validation."""

    is_valid: bool
    reason: str
    risk_score: int = 0


class LLMAnalysis(NamedTuple):
    """LLM analysis result container."""

    must_trade: bool
    confidence: float
    reason: str
    entry_price: float
    stop_loss: float
    take_profit_levels: list[float]
    risk_score: int
    position_size_pct: float


class RiskManager:
    """Validates trading decisions against risk management rules."""

    def __init__(self, config: TradingConfig):
        """Initialize risk manager.

        Args:
            config: Trading configuration with risk parameters.
        """
        self.config = config
        self._daily_loss_pct = 0.0

    def validate(
        self,
        analysis: LLMAnalysis,
        current_price: float
    ) -> RiskValidationResult:
        """Validate LLM analysis against risk management rules.

        Args:
            analysis: LLM analysis result to validate.
            current_price: Current market price of the asset.

        Returns:
            RiskValidationResult with validation status and reason.
        """
        # Rule 1: Check if LLM recommends trading
        if not analysis.must_trade:
            return RiskValidationResult(
                is_valid=False,
                reason="LLM does not recommend trading",
                risk_score=analysis.risk_score
            )

        # Rule 2: Check maximum position size
        if analysis.position_size_pct > self.config.max_position_pct:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Position size {analysis.position_size_pct}% exceeds max {self.config.max_position_pct}%",
                risk_score=analysis.risk_score
            )

        # Rule 3: Check stop loss is less than entry price (for long positions)
        if analysis.stop_loss >= analysis.entry_price:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Stop loss {analysis.stop_loss} must be less than entry {analysis.entry_price}",
                risk_score=analysis.risk_score
            )

        # Rule 4: Check risk score
        if analysis.risk_score > self.config.max_risk_score:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Risk score {analysis.risk_score} exceeds maximum {self.config.max_risk_score}",
                risk_score=analysis.risk_score
            )

        # Rule 5: Check daily loss limit
        if self._daily_loss_pct >= self.config.max_daily_loss_pct:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Daily loss {self._daily_loss_pct:.2f}% reached limit {self.config.max_daily_loss_pct}%",
                risk_score=analysis.risk_score
            )

        # Rule 6: Validate stop loss percentage
        stop_loss_pct = ((analysis.entry_price - analysis.stop_loss) / analysis.entry_price) * 100
        if stop_loss_pct < 0.5:  # Minimum 0.5% stop loss
            return RiskValidationResult(
                is_valid=False,
                reason=f"Stop loss {stop_loss_pct:.2f}% is too tight (min 0.5%)",
                risk_score=analysis.risk_score
            )

        # Rule 7: Check confidence level
        if analysis.confidence < 0.5:
            return RiskValidationResult(
                is_valid=False,
                reason=f"Confidence {analysis.confidence:.2f} is below threshold 0.5",
                risk_score=analysis.risk_score
            )

        # Rule 8: Validate take profit levels
        if not analysis.take_profit_levels:
            return RiskValidationResult(
                is_valid=False,
                reason="No take profit levels provided",
                risk_score=analysis.risk_score
            )

        # Check that all TP levels are above entry price
        for tp in analysis.take_profit_levels:
            if tp <= analysis.entry_price:
                return RiskValidationResult(
                    is_valid=False,
                    reason=f"Take profit {tp} must be above entry {analysis.entry_price}",
                    risk_score=analysis.risk_score
                )

        logger.info(
            "Risk validation passed",
            ticker="unknown",
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            risk_score=analysis.risk_score,
            position_size_pct=analysis.position_size_pct
        )

        return RiskValidationResult(
            is_valid=True,
            reason="All risk checks passed",
            risk_score=analysis.risk_score
        )

    def update_daily_loss(self, loss_pct: float) -> None:
        """Update daily loss tracking.

        Args:
            loss_pct: Daily loss percentage (positive value for losses).
        """
        self._daily_loss_pct = loss_pct
        logger.debug("Daily loss updated", loss_pct=loss_pct)

    def reset_daily_loss(self) -> None:
        """Reset daily loss tracker (call at start of new trading day)."""
        self._daily_loss_pct = 0.0
        logger.info("Daily loss tracker reset")

    def get_remaining_daily_loss(self) -> float:
        """Get remaining daily loss allowance.

        Returns:
            Remaining daily loss percentage available.
        """
        return max(0.0, self.config.max_daily_loss_pct - self._daily_loss_pct)
