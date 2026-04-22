#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тестовый скрипт для проверки qwen2.5:1.5b с увеличенным таймаутом."""
import asyncio
import sys
from pathlib import Path

# Fix импортов для Windows
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import LLMConfig
from llm.ollama_client import OllamaClient
from pydantic import BaseModel, Field

class TestResponse(BaseModel):
    """Простая модель для теста."""
    answer: str = Field(description="Краткий ответ")
    confidence: float = Field(description="Уверенность 0-1")
    tokens_used: int = Field(description="Оценка использованных токенов")

async def main():
    config = LLMConfig()
    print(f"🔍 Тест модели: {config.model}")
    print(f"⏱️ Таймаут: {config.timeout}с, max_tokens: {config.num_predict}")
    
    client = OllamaClient(config)
    
    prompt = "Сколько будет 2+2? Ответь кратко в формате JSON."
    
    try:
        print("📤 Отправка запроса...")
        result = await client.query_structured(prompt, TestResponse)
        print(f"✅ Успех: {result}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)