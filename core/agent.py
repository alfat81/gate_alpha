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
    """Модель ответа LLM для торгового сигнала."""
    entry_price: float = Field(description="Рекомендуемая цена входа")
    stop_loss: float = Field(description="Цена стоп-лосса")
    position_pct: float = Field(description="Процент от депозита для позиции (0-100)")
    reason: str = Field(description="Обоснование решения")
    confidence: float = Field(description="Уверенность в сигнале (0.0-1.0)")
    risk_score: int = Field(description="Оценка риска (1-10)")


class AlphaTradingAgent:
    """Оркестратор торгового агента."""

    def __init__(
        self,
        gate_config: GateConfig,
        llm_client: OllamaClient,
        trading_config: TradingConfig
    ):
        self.gate_config = gate_config
        self.llm_client = llm_client
        self.trading_config = trading_config

        self.scanner = AlphaScanner(gate_config, llm_client=llm_client)
        self.risk_manager = RiskManager(trading_config)
        self.grid_manager = GridManager()
        
        self.logger = logging.getLogger(f"{__name__}.AlphaTradingAgent")

    async def run_demo(self, cycles: int = 3) -> None:
        """Запускает демонстрационный цикл торговли."""
        self.logger.info(f"Запуск демо-агента на {cycles} циклов...")
        
        for i in range(1, cycles + 1):
            self.logger.info(f"--- ЦИКЛ {i}/{cycles} ---")
            
            try:
                # 1. Сканирование
                pairs = await self.scanner.scan_alpha_pairs(limit=5)
                
                if not pairs:
                    self.logger.info("Подходящих пар не найдено. Ожидание...")
                    await asyncio.sleep(5)
                    continue

                # Берём лучшую пару
                target = pairs[0]
                pair_name = target["currency_pair"]
                current_price = target["price"]
                change_24h = target["change_24h"]
                
                self.logger.info(f"Анализируем пару: {pair_name} (Цена: {current_price}, Изм: {change_24h}%)")

                # 2. Формирование промпта
                prompt = ENTRY_ANALYSIS_PROMPT.format(
                    pair=pair_name,
                    price=current_price,
                    change_24h=change_24h,
                    volume=target["volume_usd"]
                )

                # 3. Запрос к LLM
                try:
                    signal: EntrySignal = await self.llm_client.query_structured(
                        prompt=prompt,
                        response_model=EntrySignal
                    )
                    self.logger.info(f"LLM Сигнал: {signal.reason} (Уверенность: {signal.confidence})")
                except Exception as e:
                    self.logger.error(f"Ошибка получения ответа от LLM: {e}")
                    await asyncio.sleep(5)
                    continue

                # 4. Валидация рисков
                is_valid, msg = self.risk_manager.validate_trade(signal, balance=1000.0)

                if not is_valid:
                    self.logger.warning(f"Риск-менеджмент отклонил сделку: {msg}")
                    await asyncio.sleep(5)
                    continue

                self.logger.info("✅ Вход подтверждён риск-менеджером.")

                # 5. Генерация сетки ордеров
                grid_orders = self.grid_manager.generate_exit_grid(
                    entry_price=signal.entry_price,
                    total_amount_usd=1000.0 * (signal.position_pct / 100.0),
                    current_price=current_price
                )

                self.logger.info("📊 Сгенерирована сетка фиксации прибыли:")
                for idx, order in enumerate(grid_orders, 1):
                    self.logger.info(
                        f"  Уровень {idx}: Цена={order['price']:.6f}, "
                        f"Объем={order['amount_usd']:.2f}$ (+{order['take_profit_pct']}%)"
                    )

                self.logger.info(f"Демо-ордер для {pair_name} готов к размещению (симуляция).")

            except Exception as e:
                self.logger.error(f"Критическая ошибка в цикле агента: {e}", exc_info=True)

            # Пауза между циклами
            if i < cycles:
                self.logger.info("Пауза 5 секунд перед следующим циклом...")
                await asyncio.sleep(5)

        self.logger.info("Демо-цикл завершён.")