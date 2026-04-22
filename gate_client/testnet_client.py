# -*- coding: utf-8 -*-
"""
gate_client/testnet_client.py — Обёртка над Gate.io Spot API v4 (SDK 7.1.8).
API Reference: https://github.com/gateio/gateapi-python
"""
import logging
from typing import Optional, List, Dict
import gate_api
from gate_api import ApiException
from config.settings import GateConfig

logger = logging.getLogger(__name__)

# Пары для мониторинга на testnet
MONITORED_PAIRS = [
    "ETH_USD1", "BTC_USD1", "IKA_USD1", "PEPE_USD1", 
    "ETH_GUSD", "BTC_GUSD", "ETH_USDT", "BTC_USDT"
]

class TestnetSpotApi:
    """Клиент для Gate.io Testnet (SDK v7.1.8)."""
    
    def __init__(self, config: GateConfig):
        self.config = config
        
        # Настройка API клиента
        configuration = gate_api.Configuration(
            host=config.base_url,
            key=config.api_key,
            secret=config.api_secret
        )
        self.api_client = gate_api.ApiClient(configuration)
        self.api_client.set_default_header("User-Agent", "GateAlphaAgent/1.0")
        
        # 🔧 Все спот-операции через SpotApi (SDK v7.1.8)
        self.spot_api = gate_api.SpotApi(self.api_client)
    
    def get_portfolio_balance(self) -> Dict[str, float]:
        """
        Возвращает баланс портфеля {валюта: количество}.
        Метод: spot_api.list_spot_accounts()
        """
        try:
            # ✅ Правильный вызов согласно SDK 7.1.8
            accounts = self.spot_api.list_spot_accounts()
            
            balance = {}
            for acc in accounts:
                try:
                    available = float(acc.available) if acc.available else 0
                    if available > 0:
                        balance[acc.currency] = available
                except (ValueError, TypeError):
                    continue
            
            logger.debug(f"Баланс: {balance}")
            return balance
            
        except ApiException as e:
            # 🔧 400 на testnet при пустом балансе — норма
            if e.status == 400:
                logger.debug("Баланс testnet: 400 (пустой) — ожидаемо")
                return {}
            logger.warning(f"API баланс ({e.status}): {e.reason}")
            return {}
        except Exception as e:
            logger.debug(f"Баланс недоступен: {type(e).__name__}")
            return {}
    
    def get_open_orders(self, currency_pair: Optional[str] = None) -> List[Dict]:
        """
        Получает открытые ордера.
        🔧 currency_pair ОБЯЗАТЕЛЕН в list_orders() (SDK v7.1.8)
        """
        if not currency_pair:
            logger.debug("get_open_orders: currency_pair не указан")
            return []
        
        try:
            # ✅ Правильный вызов: оба параметра обязательны
            orders = self.spot_api.list_orders(
                currency_pair=currency_pair,
                status='open'
            )
            return [self._order_to_dict(o) for o in orders]
            
        except ApiException as e:
            # 🔧 400 для несуществующих пар на testnet — не ошибка
            if e.status == 400:
                logger.debug(f"Пара {currency_pair} недоступна на testnet")
                return []
            logger.warning(f"API ордеров {currency_pair}: {e.status}")
            return []
        except Exception as e:
            logger.debug(f"Ошибка ордеров {currency_pair}: {type(e).__name__}")
            return []
    
    def create_limit_order(
        self,
        currency_pair: str,
        side: str,
        amount: float,
        price: float,
        text: Optional[str] = None
    ) -> Optional[Dict]:
        """Размещает лимитный ордер."""
        try:
            order_req = gate_api.Order(
                currency_pair=currency_pair,
                type='limit',
                side=side,
                amount=str(amount),
                price=str(price),
                text=text or f"alpha_grid_{side}"
            )
            response = self.spot_api.create_order(order_req)
            logger.info(f"✅ Ордер: {response.id} | {currency_pair} {side} {amount}@{price}")
            return self._order_to_dict(response)
        except ApiException as e:
            logger.error(f"API ордер: {e.status} - {e.reason}")
            return None
        except Exception as e:
            logger.error(f"Ошибка ордера: {e}")
            return None
    
    def cancel_order(self, currency_pair: str, order_id: str) -> bool:
        """Отменяет ордер по ID."""
        try:
            self.spot_api.cancel_order(order_id=order_id, currency_pair=currency_pair)
            logger.info(f"❌ Отменён: {order_id}")
            return True
        except Exception as e:
            logger.warning(f"Ошибка отмены: {e}")
            return False
    
    def has_grid_orders(self, currency_pair: str, grid_prefix: str = "grid_tp_") -> bool:
        """Проверяет наличие сетки ордеров."""
        orders = self.get_open_orders(currency_pair)
        return any(o.get('text', '').startswith(grid_prefix) for o in orders)
    
    def get_active_positions(self) -> List[Dict]:
        """Возвращает активные позиции (перебор известных пар)."""
        positions = {}
        
        for pair in MONITORED_PAIRS:
            orders = self.get_open_orders(pair)
            if not orders:
                continue
                
            positions[pair] = {
                'currency_pair': pair,
                'buy_orders': sum(1 for o in orders if o['side'] == 'buy'),
                'sell_orders': sum(1 for o in orders if o['side'] == 'sell'),
                'total_amount': sum(float(o['amount']) for o in orders if o['side'] == 'sell'),
                'has_grid': any(o.get('text', '').startswith('grid_tp_') for o in orders)
            }
        
        return list(positions.values())
    
    @staticmethod
    def _order_to_dict(order) -> Dict:
        """Конвертирует gate_api.Order в Dict."""
        return {
            'id': getattr(order, 'id', ''),
            'currency_pair': getattr(order, 'currency_pair', ''),
            'type': getattr(order, 'type', ''),
            'side': getattr(order, 'side', ''),
            'amount': float(getattr(order, 'amount', 0) or 0),
            'price': float(getattr(order, 'price', 0) or 0),
            'filled_amount': float(getattr(order, 'filled_amount', 0) or 0),
            'status': getattr(order, 'status', ''),
            'text': getattr(order, 'text', ''),
            'create_time': getattr(order, 'create_time', 0)
        }