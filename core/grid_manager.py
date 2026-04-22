# -*- coding: utf-8 -*-
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class GridManager:
    """
    Генератор сетки тейк-профит ордеров.
    Поддерживает уровни Фибоначчи для импульсных волн.
    """
    
    # Расширения Фибоначчи для импульсных волн (1.272, 1.414, 1.618, 2.0, 2.618)
    FIB_EXTENSIONS = [1.272, 1.414, 1.618, 2.0, 2.618]
    
    # Распределение объёма по уровням (сумма = 1.0)
    AMOUNT_SPLITS = [0.25, 0.25, 0.20, 0.15, 0.15]
    
    # Стандартные проценты ТП (альтернатива Фибоначчи)
    STANDARD_TP = [0.08, 0.15, 0.25, 0.40, 0.60]

    def generate_exit_grid(
        self,
        entry_price: float,
        total_amount_usd: float,
        current_price: float,
        use_fib: bool = True
    ) -> List[Dict]:
        """
        Генерирует 5 уровней тейк-профит для фиксации прибыли.
        
        Args:
            entry_price: Цена входа в позицию
            total_amount_usd: Общий объём позиции в USD
            current_price: Текущая рыночная цена
            use_fib: Если True — использовать уровни Фибоначчи, иначе — стандартные %
            
        Returns:
            Список словарей с параметрами ордеров:
            [
                {
                    "price": float,           # Цена ордера
                    "amount_usd": float,      # Объём в USD
                    "take_profit_pct": float, # Процент прибыли
                    "fib_level": str|None     # Уровень Фибоначчи (если используется)
                },
                ...
            ]
        """
        orders = []
        
        # Выбираем уровни: Фибоначчи или стандартные
        levels = self.FIB_EXTENSIONS if use_fib else self.STANDARD_TP
        
        for idx, (level, split) in enumerate(zip(levels, self.AMOUNT_SPLITS)):
            # Рассчитываем цену ордера
            order_price = entry_price * level
            
            # Рассчитываем объём в USD для этого уровня
            amount_usd = total_amount_usd * split
            
            # Процент прибыли относительно входа
            tp_pct = round((level - 1) * 100, 1)
            
            orders.append({
                "price": round(order_price, 8),  # 8 знаков для крипто-пар
                "amount_usd": round(amount_usd, 2),
                "take_profit_pct": tp_pct,
                "fib_level": str(level) if use_fib else None,
                "text": f"grid_tp_{idx + 1}"  # Идентификатор для отслеживания
            })
        
        logger.debug(f"Сгенерировано {len(orders)} уровней сетки: вход={entry_price}, объём=${total_amount_usd}")
        return orders

    def generate_trailing_grid(
        self,
        entry_price: float,
        total_amount_usd: float,
        trail_start_pct: float = 5.0,
        trail_step_pct: float = 3.0
    ) -> List[Dict]:
        """
        Генерирует сетку с трейлинг-стоп логикой.
        
        Args:
            entry_price: Цена входа
            total_amount_usd: Общий объём позиции
            trail_start_pct: Процент, после которого активируется трейлинг
            trail_step_pct: Шаг подтяжки стоп-лосса
            
        Returns:
            Список ордеров с параметрами для трейлинг-сетки
        """
        orders = []
        current_tp = entry_price * (1 + trail_start_pct / 100)
        
        for idx, split in enumerate(self.AMOUNT_SPLITS):
            orders.append({
                "price": round(current_tp, 8),
                "amount_usd": round(total_amount_usd * split, 2),
                "take_profit_pct": round((current_tp / entry_price - 1) * 100, 1),
                "trail_step_pct": trail_step_pct,
                "text": f"trail_tp_{idx + 1}"
            })
            current_tp *= (1 + trail_step_pct / 100)
        
        return orders