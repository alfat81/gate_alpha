#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import asyncio
import logging
from pathlib import Path

# Fix для Windows
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import GateConfig, LLMConfig, TradingConfig
from core.agent import AlphaTradingAgent
from llm.ollama_client import OllamaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def main():
    gate_config = GateConfig.testnet()
    llm_config = LLMConfig()
    trading_config = TradingConfig()

    ollama = OllamaClient(llm_config)
    try:
        models = await ollama.client.list()
        logger.info(f"✓ Ollama готов: {len(models['models'])} моделей")
    except Exception as e:
        logger.error(f"✗ Ошибка Ollama: {e}")
        return

    agent = AlphaTradingAgent(
        gate_config=gate_config,
        llm_client=ollama,
        trading_config=trading_config
    )

    logger.info("🔄 Запуск агента в режиме testnet...")
    await agent.run_demo(cycles=3)
    logger.info("✅ Демо-цикл завершён")

if __name__ == "__main__":
    asyncio.run(main())