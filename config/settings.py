import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class GateConfig:
    """Конфигурация Gate.io API"""
    base_url: str
    api_key: str
    api_secret: str
    timeout: int = 30
    
    @classmethod
    def testnet(cls) -> 'GateConfig':
        """Конфигурация для тестовой сети [[38]]"""
        return cls(
            base_url=os.getenv('GATE_TESTNET_URL', 'https://api-testnet.gateapi.io/api/v4'),
            api_key=os.getenv('GATE_API_KEY', ''),
            api_secret=os.getenv('GATE_API_SECRET', ''),
        )
    
    @classmethod
    def production(cls) -> 'GateConfig':
        """Конфигурация для реальной торговли"""
        return cls(
            base_url=os.getenv('GATE_PROD_URL', 'https://api.gateio.ws/api/v4'),
            api_key=os.getenv('GATE_API_KEY', ''),
            api_secret=os.getenv('GATE_API_SECRET', ''),
        )

@dataclass
class LLMConfig:
    """Конфигурация Ollama"""
@dataclass
class LLMConfig:
    model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")  # ← изменено
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    temperature: float = 0.15  # Qwen стабильнее при 0.1-0.2
    format: str = "json"
@dataclass
class TradingConfig:
    """Торговые параметры для Alpha-секции"""
    max_position_pct: float = 3.0      # Макс. 3% депозита на сделку
    stop_loss_pct: float = 10.0        # Стоп-лосс 10%
    grid_levels: int = 5               # Уровней сетки выхода
    take_profit_levels: list = None    # Профили ТП
    
    def __post_init__(self):
        if self.take_profit_levels is None:
            self.take_profit_levels = [0.08, 0.15, 0.25, 0.40, 0.60]