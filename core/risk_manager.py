# -*- coding: utf-8 -*-
import logging
from typing import Tuple, Any
from config.settings import TradingConfig

logger = logging.getLogger(__name__)

class RiskManager:
    """Валидатор торговых сигналов на основе правил риск-менеджмента."""
    def __init__(self, config: TradingConfig):
        self.config = config

    def validate_trade(self, signal: Any, balance: float) -> Tuple[bool, str]:
        if not signal:
            return False, "Пустой сигнал от LLM"
        if signal.position_pct > self.config.max_position_pct:
            return False, f"Позиция {signal.position_pct}% превышает лимит {self.config.max_position_pct}%"
        if signal.stop_loss >= signal.entry_price:
            return False, "Stop-loss должен быть строго ниже entry_price"
        if signal.risk_score > 8:
            return False, f"Риск-скор {signal.risk_score} слишком высокий (макс. 8)"
        required = balance * (signal.position_pct / 100.0)
        if required > balance:
            return False, "Недостаточно средств на балансе"
        return True, "OK"