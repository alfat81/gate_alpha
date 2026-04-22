#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gate Alpha Trading Agent — точка входа.
Запускает агента в режиме testnet с локальной LLM (Ollama + qwen2.5:1.5b).
"""
import sys
import asyncio
import logging
from pathlib import Path

# =============================================================================
# FIX ДЛЯ WINDOWS: добавляем корень проекта в sys.path для импортов
# =============================================================================
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# =============================================================================
# ИМПОРТЫ ПРОЕКТА
# =============================================================================
from config.settings import GateConfig, LLMConfig, TradingConfig
from core.agent import AlphaTradingAgent
from llm.ollama_client import OllamaClient

# =============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ (файл + консоль)
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8", mode="a"),
        logging.StreamHandler()
    ]
)
# ✅ КРИТИЧНО: __name__ с двумя подчёркиваниями с каждой стороны
logger = logging.getLogger(__name__)


async def main():
    """Точка входа: инициализация и запуск агента."""
    
    # =============================================================================
    # 🎛️ КОНФИГУРАЦИЯ ЗАПУСКА
    # =============================================================================
    PLACE_ORDERS = False  # 🔥 True = размещать реальные ордера на testnet
    CYCLES = 3            # Количество циклов сканирования
    
    logger.info("=" * 80)
    logger.info("🚀 GATE ALPHA TRADING AGENT")
    logger.info("=" * 80)
    
    # 1. Инициализация конфигурации
    gate_config = GateConfig.testnet()
    llm_config = LLMConfig()
    trading_config = TradingConfig()

    # 2. Проверка подключения к Ollama
    ollama = OllamaClient(llm_config)
    try:
        # ✅ Асинхронный вызов: await обязателен для AsyncClient
        models = await ollama.client.list()
        logger.info(f"✓ Ollama готов: {len(models['models'])} моделей")
        for model in models['models']:
            logger.info(f"  - {model['name']} ({model['size']})")
    except Exception as e:
        logger.error(f"✗ Ошибка подключения к Ollama: {e}")
        return

    # 3. Создание агента
    agent = AlphaTradingAgent(
        gate_config=gate_config,
        llm_client=ollama,
        trading_config=trading_config
    )

    # 4. Запуск цикла агента
    mode_str = "🔴 РЕАЛЬНЫЕ ОРДЕРА (TESTNET)" if PLACE_ORDERS else "🟢 СИМУЛЯЦИЯ (без ордеров)"
    logger.info(f"🔄 Запуск агента: {mode_str}")
    logger.info(f"📊 Циклов: {CYCLES}")
    logger.info("=" * 80)
    
    await agent.run_demo(cycles=CYCLES, place_orders=PLACE_ORDERS)
    
    logger.info("=" * 80)
    logger.info("✅ Демо-цикл завершён")
    logger.info("=" * 80)


# =============================================================================
# ТОЧКА ВХОДА В МОДУЛЬ
# =============================================================================
# ✅ КРИТИЧНО: __name__ и "__main__" с двумя подчёркиваниями
if __name__ == "__main__":
    asyncio.run(main())