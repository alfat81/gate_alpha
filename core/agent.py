# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Optional
from pydantic import BaseModel, Field

from config.settings import GateConfig, TradingConfig
from config.prompts import ENTRY_ANALYSIS_PROMPT
from llm.ollama_client import OllamaClient
from core.scanner import AlphaScanner
from core.risk_manager import RiskManager
from core.grid_manager import GridManager

logger = logging.getLogger(__name__)

class EntrySignal(BaseModel):
    entry_price: float = Field(description="Рекомендуемая цена входа")
    stop_loss: float = Field(description="Цена стоп-лосса")
    position_pct: float = Field(description="Процент от депозита (0-100)")
    reason: str = Field(description="Обоснование")
    confidence: float = Field(description="Уверенность (0.0-1.0)")
    risk_score: int = Field(description="Риск (1-10)")

class AlphaTradingAgent:
    def __init__(
        self,
        gate_config: GateConfig,
        llm_client: OllamaClient,
        trading_config: TradingConfig
    ):
        self.gate_config = gate_config
        self.llm_client = llm_client  # ← исправлено: убран пробел
        self.trading_config = trading_config

        self.scanner = AlphaScanner(gate_config)  # LLM-конфиг отключён в scanner
        self.risk_manager = RiskManager(trading_config)
        self.grid_manager = GridManager()  # ← исправлено: убран пробел
        
        self.logger = logging.getLogger(f"{__name__}.AlphaTradingAgent")

    async def run_demo(self, cycles: int = 3) -> None:
        self.logger.info(f"Запуск демо-агента на {cycles} циклов...")
        
        for i in range(1, cycles + 1):
            self.logger.info(f"--- ЦИКЛ {i}/{cycles} ---")
            
            try:
                pairs = await self.scanner.scan_alpha_pairs(limit=5)
                
                if not pairs:
                    self.logger.info("Подходящих пар не найдено. Ожидание...")
                    await asyncio.sleep(5)
                    continue

                target = pairs[0]
                pair_name = target["currency_pair"]
                current_price = target["price"]
                change_24h = target["change_24h"]
                
                self.logger.info(f"Анализируем пару: {pair_name} (Цена: {current_price}, Изм: {change_24h}%)")

                prompt = ENTRY_ANALYSIS_PROMPT.format(
                    pair=pair_name,
                    price=current_price,
                    change_24h=change_24h,
                    volume=target["volume_usd"]
                )

                try:
                    signal: EntrySignal = await self.llm_client.query_structured(
                        prompt=prompt,
                        response_model=EntrySignal  # ← исправлено: schema → response_model
                    )
                    self.logger.info(f"LLM Сигнал: {signal.reason} (Уверенность: {signal.confidence})")
                except Exception as e:
                    self.logger.warning(f"⚠️ LLM недоступен, используем дефолтный сигнал")
                    # Дефолтный сигнал для демо
                    signal = EntrySignal(
                        entry_price=current_price * 0.99,
                        stop_loss=current_price * 0.90,
                        position_pct=2.0,
                        reason="Fallback: LLM недоступен",
                        confidence=0.5,
                        risk_score=5
                    )

                is_valid, msg = self.risk_manager.validate_trade(signal, balance=1000.0)
                if not is_valid:
                    self.logger.warning(f"Риск-менеджмент отклонил: {msg}")
                    await asyncio.sleep(5)
                    continue

                self.logger.info("✅ Вход подтверждён.")

                grid_orders = self.grid_manager.generate_exit_grid(
                    entry_price=signal.entry_price,
                    total_amount_usd=1000.0 * (signal.position_pct / 100.0),
                    current_price=current_price
                )

                self.logger.info("📊 Сетка выхода:")
                for idx, order in enumerate(grid_orders, 1):
                    self.logger.info(
                        f"  {idx}: Цена={order['price']:.6f}, "
                        f"Объём=${order['amount_usd']:.2f} (+{order['take_profit_pct']}%)"
                    )

            except Exception as e:
                self.logger.error(f"Ошибка в цикле: {e}", exc_info=True)

            if i < cycles:
                await asyncio.sleep(5)

        self.logger.info("Демо-цикл завершён.")