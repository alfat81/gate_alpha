# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import List, Dict, Any, Optional

import gate_api
from gate_api import ApiException
from pydantic import BaseModel, Field

from config.settings import GateConfig
from llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ScannerConfig(BaseModel):
    """Динамическая конфигурация фильтров от LLM."""
    min_volatility_pct: float = Field(ge=0, le=100, description="Мин. |изменение 24ч| в %")
    min_volume_usd: float = Field(ge=0, description="Мин. объём в USD")
    max_volume_usd: Optional[float] = Field(default=None, description="Макс. объём в USD (опционально)")
    exclude_quotes: List[str] = Field(default=["USDT", "USDC", "BTC", "ETH"])
    reason: str = Field(description="Обоснование выбранных параметров")


class AlphaScanner:
    """Сканер рынка с LLM-адаптивной фильтрацией."""
    
    DEFAULT_CONFIG = ScannerConfig(
        min_volatility_pct=5.0,
        min_volume_usd=10_000,
        max_volume_usd=5_000_000,
        exclude_quotes=["USDT", "USDC", "BTC", "ETH"],
        reason="Default fallback for testnet"
    )
    
    def __init__(self, gate_config: GateConfig, llm_client: Optional[OllamaClient] = None):
        self.config = gate_config
        self.llm_client = llm_client
        self.api_client = gate_api.ApiClient()
        self.api_client.host = gate_config.base_url
        self.api_client.key = gate_config.api_key
        self.api_client.secret = gate_config.api_secret
        self.api_client.set_default_header("User-Agent", "GateAlphaAgent/1.0")

    async def get_llm_scanner_config(self, market_summary: Dict[str, Any]) -> ScannerConfig:
        """Запрашивает у LLM оптимальные параметры фильтрации."""
        if not self.llm_client:
            logger.warning("LLM-клиент не подключён, используем дефолтные фильтры")
            return self.DEFAULT_CONFIG
        
        prompt = f"""
Ты — аналитик крипторынка. На основе сводки определи оптимальные фильтры для поиска волатильных пар.

РЫНОЧНАЯ СВОДКА:
- Всего пар: {market_summary['total_pairs']}
- Среднее изменение 24ч: {market_summary['avg_change']:.2f}%
- Медианный объём: ${market_summary['median_volume']:,.0f}
- Макс. изменение: {market_summary['max_change']:.2f}%
- Пар с |Δ|>10%: {market_summary['volatile_count']}

ЗАДАЧА:
Предложи параметры фильтрации для Alpha-секции (высокорискованные активы).
Верни СТРОГО JSON:
{{
  "min_volatility_pct": число (3-30),
  "min_volume_usd": число (>0),
  "max_volume_usd": число или null,
  "exclude_quotes": ["USDT", "USDC", "BTC", "ETH"],
  "reason": "краткое обоснование"
}}
"""
        try:
            config = await self.llm_client.query_structured(
                prompt=prompt,
                response_model=ScannerConfig
            )
            logger.info(f"🤖 LLM-конфиг: {config.reason}")
            return config
        except Exception as e:
            logger.warning(f"Ошибка получения конфига от LLM: {e}, используем дефолт")
            return self.DEFAULT_CONFIG

    async def scan_alpha_pairs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Сканирует рынок с адаптивными фильтрами."""
        api_instance = gate_api.SpotApi(gate_api.ApiClient())
        api_instance.api_client.host = self.config.base_url
        api_instance.api_client.key = self.config.api_key
        api_instance.api_client.secret = self.config.api_secret

        try:
            logger.info("🔍 Загрузка тикеров...")
            # gate-api SDK синхронный → оборачиваем в thread
            tickers = await asyncio.to_thread(api_instance.list_tickers)
        except ApiException as e:
            logger.error(f"API ошибка: {e.status} - {e.reason}")
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки тикеров: {e}")
            return []

        # Сбор статистики для LLM
        changes = []
        volumes = []
        for t in tickers:
            if t.change_percentage:
                try:
                    changes.append(abs(float(t.change_percentage)))
                except:
                    pass
            if t.base_volume and t.last:
                try:
                    vol = float(t.base_volume) * float(t.last)
                    volumes.append(vol)
                except:
                    pass
        
        market_summary = {
            "total_pairs": len(tickers),
            "avg_change": sum(changes)/len(changes) if changes else 0,
            "median_volume": sorted(volumes)[len(volumes)//2] if volumes else 0,
            "max_change": max(changes) if changes else 0,
            "volatile_count": sum(1 for c in changes if c > 10)
        }

        # Получаем конфиг от LLM (или дефолт)
        filters = await self.get_llm_scanner_config(market_summary)
        
        # Применение фильтров
        candidates = []
        excluded = set(filters.exclude_quotes)
        
        for t in tickers:
            if not t.currency_pair:
                continue
            try:
                pair = t.currency_pair
                last_price = float(t.last) if t.last else 0.0
                change_pct = float(t.change_percentage) if t.change_percentage else 0.0
                base_vol = float(t.base_volume) if t.base_volume else 0.0
                volume_usd = base_vol * last_price
                
                parts = pair.split("_")
                if len(parts) != 2:
                    continue
                _, quote = parts
                
                # Динамические фильтры
                if quote in excluded:
                    continue
                if abs(change_pct) < filters.min_volatility_pct:
                    continue
                if volume_usd < filters.min_volume_usd:
                    continue
                if filters.max_volume_usd and volume_usd > filters.max_volume_usd:
                    continue
                
                score = abs(change_pct) * (volume_usd ** 0.5)
                candidates.append({
                    "currency_pair": pair,
                    "price": last_price,
                    "change_24h": change_pct,
                    "volume_usd": volume_usd,
                    "score": score
                })
            except (ValueError, TypeError):
                continue

        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        result = [
            {k: v for k, v in item.items() if k != "score"}
            for item in candidates[:limit]
        ]
        
        logger.info(f"✅ Найдено {len(result)} пар (фильтры: Δ>{filters.min_volatility_pct}%, vol>${filters.min_volume_usd:,.0f})")
        return result