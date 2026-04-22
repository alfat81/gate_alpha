#!/usr/bin/env python3
import asyncio
import logging
from config.settings import GateConfig, LLMConfig, TradingConfig
from core.agent import AlphaTradingAgent
from llm.ollama_client import OllamaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # 1. Инициализация конфигурации
    gate_config = GateConfig.testnet()  # ← По умолчанию testnet!
    llm_config = LLMConfig()
    trading_config = TradingConfig()
    
    # 2. Проверка подключения к Ollama
    ollama = OllamaClient(llm_config)
    try:
        models = ollama.client.list()
        logger.info(f"✓ Ollama готов: {len(models['models'])} моделей")
    except Exception as e:
        logger.error(f"✗ Не удалось подключиться к Ollama: {e}")
        return
    
    # 3. Создание агента
    agent = AlphaTradingAgent(
        gate_config=gate_config,
        llm_client=ollama,
        trading_config=trading_config
    )
    
    # 4. Запуск цикла (в демо-режиме для testnet)
    logger.info("🔄 Запуск агента в режиме testnet...")
    await agent.run_demo(cycles=3)  # 3 итерации для теста
    
    logger.info("✅ Демо-цикл завершён")

if __name__ == "__main__":
    asyncio.run(main())