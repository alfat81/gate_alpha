# -*- coding: utf-8 -*-
"""
core/agent.py — Оркестратор торгового агента.
Управляет циклом: Портфель -> Сканирование -> LLM-анализ (ТА/Волны) -> Риск -> Сетка -> Размещение на бирже.
"""
import asyncio
import logging
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

from config.settings import GateConfig, TradingConfig
from config.prompts import ENTRY_ANALYSIS_PROMPT
from llm.ollama_client import OllamaClient
from core.scanner import AlphaScanner
from core.risk_manager import RiskManager
from core.grid_manager import GridManager
from gate_client.testnet_client import TestnetSpotApi

logger = logging.getLogger(__name__)


class EntrySignal(BaseModel):
    """Модель ответа LLM с поддержкой ТА и волнового анализа."""
    entry_price: float = Field(description="Рекомендуемая цена входа")
    stop_loss: float = Field(description="Цена стоп-лосса (должна быть < entry_price для long)")
    position_pct: float = Field(default=2.0, ge=1.0, le=10.0, description="Процент от депозита (1-10%)")
    reason: str = Field(default="TA analysis", description="Обоснование решения")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Уверенность в сигнале (0.0-1.0)")
    risk_score: int = Field(default=5, ge=1, le=10, description="Оценка риска (1-10)")
    
    # 🔥 Поля для технического анализа и волн Эллиотта
    wave_phase: str = Field(default="unknown", description="Фаза волны: импульс 1/3/5 или коррекция A/B/C")
    support_level: Optional[float] = Field(default=None, description="Ближайший уровень поддержки")
    resistance_level: Optional[float] = Field(default=None, description="Ближайший уровень сопротивления")


class AlphaTradingAgent:
    """Оркестратор торгового агента с размещением ордеров на бирже."""

    GRID_PREFIX = "grid_tp_"

    def __init__(
        self,
        gate_config: GateConfig,
        llm_client: OllamaClient,
        trading_config: TradingConfig
    ):
        self.gate_config = gate_config
        self.llm_client = llm_client  # ✅ ИСПРАВЛЕНО: убран пробел
        self.trading_config = trading_config

        self.scanner = AlphaScanner(gate_config, llm_client=llm_client)
        self.risk_manager = RiskManager(trading_config)
        self.grid_manager = GridManager()  # ✅ ИСПРАВЛЕНО: убран пробел
        self.exchange = TestnetSpotApi(gate_config)
        
        self.logger = logging.getLogger(f"{__name__}.AlphaTradingAgent")

    async def run_demo(self, cycles: int = 3, place_orders: bool = False) -> None:
        mode_str = "✅ РЕАЛЬНЫЕ ОРДЕРА" if place_orders else "🧪 СИМУЛЯЦИЯ"
        self.logger.info(f"Запуск агента на {cycles} циклов (режим: {mode_str})")
        
        for i in range(1, cycles + 1):
            self.logger.info(f"--- ЦИКЛ {i}/{cycles} ---")
            
            try:
                portfolio = await self._analyze_portfolio()
                self.logger.info(f"📊 Портфель: {len(portfolio)} активных пар")
                
                pairs = await self.scanner.scan_alpha_pairs(limit=5)
                
                if not pairs:
                    self.logger.info("Подходящих пар не найдено. Ожидание...")
                    await asyncio.sleep(5)
                    continue

                for target in pairs:
                    await self._process_pair(target, portfolio, place_orders)
                    await asyncio.sleep(2)

            except Exception as e:
                self.logger.error(f"Критическая ошибка в цикле агента: {e}", exc_info=True)

            if i < cycles:
                self.logger.info("Пауза 10 секунд перед следующим циклом...")
                await asyncio.sleep(10)

        self.logger.info("🏁 Цикл завершён.")

    async def _analyze_portfolio(self) -> List[Dict]:
        try:
            positions = self.exchange.get_active_positions()
            balance = self.exchange.get_portfolio_balance()
            
            self.logger.info(f"💰 Баланс: {balance}")
            for pos in positions:
                grid_status = "✅ есть сетка" if pos.get('has_grid') else "❌ нет сетки"
                self.logger.info(
                    f"  {pos['currency_pair']}: buy={pos['buy_orders']}, "
                    f"sell={pos['sell_orders']}, grid={grid_status}"
                )
            return positions
        except Exception as e:
            self.logger.error(f"Ошибка анализа портфеля: {e}")
            return []

    async def _process_pair(self, target: Dict, portfolio: List[Dict], place_orders: bool) -> None:
        pair_name = target["currency_pair"]
        current_price = target["price"]
        change_24h = target["change_24h"]
        
        existing_position = next((p for p in portfolio if p['currency_pair'] == pair_name), None)
        
        if existing_position and existing_position.get('has_grid'):
            self.logger.info(f"⏭️ {pair_name}: сетка уже размещена, пропускаем")
            return
        
        self.logger.info(f"🔍 Анализируем: {pair_name} (Цена: {current_price}, Изм: {change_24h}%)")

        prompt = ENTRY_ANALYSIS_PROMPT.format(
            pair=pair_name,
            price=current_price,
            change_24h=change_24h,
            volume=target["volume_usd"]
        )

        try:
            signal: EntrySignal = await self.llm_client.query_structured(
                prompt=prompt,
                response_model=EntrySignal  # ✅ ИСПРАВЛЕНО: schema → response_model
            )
            self.logger.info(
                f"LLM Сигнал: {signal.reason} | Волна: {signal.wave_phase} "
                f"(Уверенность: {signal.confidence}, Риск: {signal.risk_score}/10)"
            )
        except Exception as e:
            self.logger.error(f"Ошибка LLM: {e}")
            return

        # 🔧 Авто-коррекция сигнала
        if signal.stop_loss >= signal.entry_price:
            signal.stop_loss = signal.entry_price * 0.98
            self.logger.warning(f"⚠️ Авто-коррекция stop_loss: {signal.stop_loss:.2f}")
        
        if signal.position_pct > self.trading_config.max_position_pct:
            signal.position_pct = self.trading_config.max_position_pct
        
        if signal.support_level is None:
            signal.support_level = signal.entry_price * 0.97
        if signal.resistance_level is None:
            signal.resistance_level = signal.entry_price * 1.03

        is_valid, msg = self.risk_manager.validate_trade(signal, balance=1000.0)
        if not is_valid:
            self.logger.warning(f"Риск-менеджмент отклонил: {msg}")
            return

        self.logger.info("✅ Вход подтверждён риск-менеджером.")

        grid_orders = self.grid_manager.generate_exit_grid(
            entry_price=signal.entry_price,
            total_amount_usd=1000.0 * (signal.position_pct / 100.0),
            current_price=current_price,
            use_fib=True
        )

        self.logger.info(f"📋 Сгенерирована сетка ({len(grid_orders)} уровней):")
        for idx, order in enumerate(grid_orders, 1):
            price_fmt = f"{order['price']:.8f}" if order['price'] < 1 else f"{order['price']:.2f}"
            self.logger.info(
                f"  {idx}: Цена={price_fmt} (×{order['fib_level']}), "
                f"Объём=${order['amount_usd']:.2f} (+{order['take_profit_pct']}%)"
            )

        if place_orders:
            await self._place_grid_orders(pair_name, grid_orders, signal.entry_price)
        else:
            self.logger.info(f"🧪 Симуляция: ордера для {pair_name} готовы к размещению")

    async def _place_grid_orders(self, currency_pair: str, grid_orders: List[Dict], entry_price: float) -> bool:
        placed_count = 0
        
        for idx, order in enumerate(grid_orders, 1):
            order_text = f"{self.GRID_PREFIX}{idx}"
            amount = order['amount_usd'] / order['price']
            
            result = self.exchange.create_limit_order(
                currency_pair=currency_pair,
                side='sell',
                amount=round(amount, 8),
                price=round(order['price'], 8),
                text=order_text
            )
            
            if result:
                placed_count += 1
                await asyncio.sleep(0.5)
            else:
                self.logger.error(f"❌ Не удалось разместить ордер {order_text}")
        
        success = placed_count == len(grid_orders)
        if success:
            self.logger.info(f"✅ Сетка размещена: {placed_count}/{len(grid_orders)} ордеров для {currency_pair}")
        else:
            self.logger.warning(f"⚠️ Частичное размещение: {placed_count}/{len(grid_orders)} ордеров")
        
        return success

    async def cancel_pair_grid(self, currency_pair: str) -> bool:
        orders = self.exchange.get_open_orders(currency_pair)
        grid_orders = [o for o in orders if o['text'].startswith(self.GRID_PREFIX)]
        
        if not grid_orders:
            self.logger.info(f"Нет ордеров сетки для {currency_pair}")
            return True
        
        cancelled = 0
        for order in grid_orders:
            if self.exchange.cancel_order(currency_pair, order['id']):
                cancelled += 1
        
        self.logger.info(f"Отменено {cancelled}/{len(grid_orders)} ордеров сетки для {currency_pair}")
        return cancelled == len(grid_orders)