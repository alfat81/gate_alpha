import asyncio
import logging
from typing import List, Dict, Any

import gate_api
from gate_api.exceptions import ApiException

from config.settings import GateConfig

logger = logging.getLogger(__name__)


class AlphaScanner:
    """
    Сканер рынка для поиска волатильных пар (Alpha-сигналов) на Gate.io.
    Фильтрует тикеры по изменению цены за 24ч, объему и исключает стейблкоины/мажоры.
    """

    def __init__(self, gate_config: GateConfig):
        self.config = gate_config
        self.api_client = gate_api.ApiClient()
        self.api_client.host = gate_config.base_url
        self.api_client.key = gate_config.api_key
        self.api_client.secret = gate_config.api_secret
        # Установка таймаута через конфигурацию клиента, если поддерживается, или через wrapper
        self.api_client.set_default_header("User-Agent", "GateAlphaAgent/1.0")

    async def scan_alpha_pairs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Сканирует рынок и возвращает топ-N пар с высоким потенциалом волатильности.
        
        Критерии фильтрации:
        - |change_24h| > 15%
        - Volume USD в диапазоне [100k, 5M]
        - Исключение пар к USDT, USDC, BTC, ETH
        
        Returns:
            Список словарей с информацией о парах.
        """
        api_instance = gate_api.SpotApi(gate_api.ApiClient())
        api_instance.api_client.host = self.config.base_url
        api_instance.api_client.key = self.config.api_key
        api_instance.api_client.secret = self.config.api_secret

        try:
            logger.info("Начало сканирования рынка...")
            # Получаем все тикеры
            # Используем asyncio.wait_for для обеспечения таймаута на уровне вызова
            tickers = await asyncio.wait_for(
                api_instance.list_tickers(),
                timeout=10.0
            )
        except ApiException as e:
            logger.error(f"API ошибка при получении тикеров: {e.status} - {e.reason}")
            return []
        except asyncio.TimeoutError:
            logger.error("Таймаут при запросе тикеров (10с)")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при сканировании: {e}")
            return []

        excluded_quotes = {"USDT", "USDC", "BTC", "ETH"}
        candidates = []

        for t in tickers:
            if not t.currency_pair:
                continue

            try:
                # Парсинг данных
                pair = t.currency_pair
                last_price = float(t.last) if t.last else 0.0
                change_pct = float(t.change_percentage) if t.change_percentage else 0.0
                
                # Объем в базовой валюте * цена = объем в коте
                base_vol = float(t.base_volume) if t.base_volume else 0.0
                volume_usd = base_vol * last_price

                # Разделение пары для проверки кота
                # Формат Gate.io обычно "BTC_USDT"
                parts = pair.split("_")
                if len(parts) != 2:
                    continue
                _, quote = parts

                # Фильтрация
                if quote in excluded_quotes:
                    continue

                if abs(change_pct) <= 15.0:
                    continue

                if not (100_000 <= volume_usd <= 5_000_000):
                    continue

                # Расчет скоринга: волатильность * объем (нормализованный)
                # Чем больше изменение и объем, тем выше приоритет
                score = abs(change_pct) * volume_usd

                candidates.append({
                    "currency_pair": pair,
                    "price": last_price,
                    "change_24h": change_pct,
                    "volume_usd": volume_usd,
                    "score": score
                })

            except (ValueError, TypeError):
                continue

        # Сортировка по скору (убывание)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        result = []
        for item in candidates[:limit]:
            result.append({
                "currency_pair": item["currency_pair"],
                "price": item["price"],
                "change_24h": item["change_24h"],
                "volume_usd": item["volume_usd"]
            })

        logger.info(f"Найдено {len(result)} потенциальных пар из {len(tickers)}")
        return result