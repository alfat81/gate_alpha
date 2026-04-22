# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()

@dataclass
class GateConfig:
    """Конфигурация подключения к Gate.io API."""
    base_url: str
    api_key: str
    api_secret: str
    
    @classmethod
    def testnet(cls) -> 'GateConfig':
        return cls(
            base_url=os.getenv('GATE_TESTNET_URL', 'https://api-testnet.gateapi.io/api/v4'),
            api_key=os.getenv('GATE_API_KEY', ''),
            api_secret=os.getenv('GATE_API_SECRET', ''),
        )

    @classmethod
    def production(cls) -> 'GateConfig':
        return cls(
            base_url=os.getenv('GATE_PROD_URL', 'https://api.gateio.ws/api/v4'),
            api_key=os.getenv('GATE_API_KEY', ''),
            api_secret=os.getenv('GATE_API_SECRET', ''),
        )

@dataclass
class LLMConfig:
    """Конфигурация Ollama (qwen2.5:1.5b)."""
    model: str = os.getenv('OLLAMA_MODEL', 'qwen2.5:1.5b')
    host: str = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    
    # Параметры генерации для маленьких моделей
    temperature: float = float(os.getenv('OLLAMA_TEMPERATURE', '0.2'))
    top_p: float = float(os.getenv('OLLAMA_TOP_P', '0.9'))
    num_predict: int = int(os.getenv('OLLAMA_NUM_PREDICT', '1024'))  # Макс. токенов ответа
    
    # Таймауты
    timeout: int = int(os.getenv('OLLAMA_TIMEOUT', '120'))  # 120 сек на ответ

@dataclass
class TradingConfig:
    """Параметры риск-менеджмента."""
    max_position_pct: float = 3.0      # Макс. % депозита в сделку
    stop_loss_pct: float = 10.0        # Дефолтный стоп-лосс %
    min_liquidity_usd: float = 1_000   # Мин. ликвидность для теста