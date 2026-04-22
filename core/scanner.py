# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import List, Dict, Any

import gate_api
from gate_api import ApiException
from config.settings import GateConfig

logger = logging.getLogger(__name__)

class AlphaScanner:
    """Сканер для testnet: упрощённые фильтры."""
    
    MIN_VOLATILITY = 3.0
    MIN_VOLUME = 1_000
    EXCLUDE_QUOTES = {"USDT", "USDC", "BTC", "ETH"}
    
    def __init__(self, gate_config: GateConfig, llm_client=None):
        self.config = gate_config
        self.api_client = gate_api.ApiClient()
        self.api_client.host = gate_config.base_url
        self.api_client.key = gate_config.api_key
        self.api_client.secret = gate_config.api_secret
        self.api_client.set_default_header("User-Agent", "GateAlphaAgent/1.0")

    async def scan_alpha_pairs(self, limit: int = 10) -> List[Dict[str, Any]]:
        api_instance = gate_api.SpotApi(gate_api.ApiClient())
        api_instance.api_client.host = self.config.base_url
        api_instance.api_client.key = self.config.api_key
        api_instance.api_client.secret = self.config.api_secret

        try:
            logger.info("🔍 Загрузка тикеров...")
            tickers = await asyncio.to_thread(api_instance.list_tickers)
        except ApiException as e:
            logger.error(f"API ошибка: {e.status} - {e.reason}")
            return []
        except Exception as e:
            logger.error(f"Ошибка загрузки: {e}")
            return []

        candidates = []
        
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
                
                if quote in self.EXCLUDE_QUOTES:
                    continue
                if abs(change_pct) < self.MIN_VOLATILITY:
                    continue
                if volume_usd < self.MIN_VOLUME:
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
        
        result = [{k: v for k, v in item.items() if k != "score"} for item in candidates[:limit]]
        
        logger.info(f"✅ Найдено {len(result)} пар (фильтры: Δ>{self.MIN_VOLATILITY}%, vol>${self.MIN_VOLUME:,})")
        return result