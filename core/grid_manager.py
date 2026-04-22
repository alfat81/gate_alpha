# -*- coding: utf-8 -*-
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class GridManager:
    """Генератор сетки тейк-профит ордеров на выход из позиции."""
    def __init__(self):
        self.tp_levels = [0.08, 0.15, 0.25, 0.40, 0.60]
        self.amount_splits = [0.25, 0.25, 0.20, 0.15, 0.15]

    def generate_exit_grid(self, entry_price: float, total_amount_usd: float, current_price: float) -> List[Dict]:
        orders = []
        for tp, split in zip(self.tp_levels, self.amount_splits):
            orders.append({
                "price": entry_price * (1 + tp),
                "amount_usd": total_amount_usd * split,
                "take_profit_pct": tp * 100
            })
        return orders