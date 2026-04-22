"""Grid order manager for generating limit sell orders."""

from dataclasses import dataclass
from typing import List

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class GridOrder:
    """Represents a grid order with price and quantity."""

    order_id: int
    take_profit_pct: float
    quantity_pct: float
    price: float
    quantity: float  # Actual quantity in base currency


class GridManager:
    """Generates grid of limit sell orders for take profit levels."""

    # Take profit percentages for each level
    TP_LEVELS = [8.0, 15.0, 25.0, 40.0, 60.0]

    # Quantity distribution for each level (must sum to 100)
    QUANTITY_PCTS = [25.0, 25.0, 20.0, 15.0, 15.0]

    def __init__(self):
        """Initialize grid manager."""
        self._order_counter = 0

    def generate_grid(
        self,
        entry_price: float,
        position_size: float,
        custom_tp_levels: List[float] | None = None
    ) -> List[GridOrder]:
        """Generate grid of limit sell orders.

        Args:
            entry_price: Entry price for the position.
            position_size: Total position size in base currency.
            custom_tp_levels: Optional custom take profit percentages.

        Returns:
            List of GridOrder objects for each take profit level.
        """
        tp_levels = custom_tp_levels if custom_tp_levels else self.TP_LEVELS
        quantity_pcts = self.QUANTITY_PCTS[:len(tp_levels)]

        # Normalize quantity percentages if using custom levels
        if custom_tp_levels and len(custom_tp_levels) != len(self.QUANTITY_PCTS):
            equal_qty = 100.0 / len(custom_tp_levels)
            quantity_pcts = [equal_qty] * len(custom_tp_levels)

        orders = []

        for i, (tp_pct, qty_pct) in enumerate(zip(tp_levels, quantity_pcts)):
            self._order_counter += 1

            # Calculate take profit price
            tp_price = entry_price * (1 + tp_pct / 100.0)

            # Calculate quantity for this level
            qty = position_size * (qty_pct / 100.0)

            order = GridOrder(
                order_id=self._order_counter,
                take_profit_pct=tp_pct,
                quantity_pct=qty_pct,
                price=round(tp_price, 8),
                quantity=round(qty, 8)
            )

            orders.append(order)

        logger.info(
            "Grid orders generated",
            entry_price=entry_price,
            position_size=position_size,
            num_orders=len(orders),
            total_quantity=sum(o.quantity for o in orders)
        )

        return orders

    def calculate_total_value(
        self,
        orders: List[GridOrder],
        prices: List[float]
    ) -> float:
        """Calculate total USD value of all grid orders.

        Args:
            orders: List of GridOrder objects.
            prices: List of prices corresponding to each order.

        Returns:
            Total USD value of all orders.
        """
        if len(orders) != len(prices):
            raise ValueError("Orders and prices lists must have same length")

        total_value = sum(order.quantity * price for order, price in zip(orders, prices))
        return round(total_value, 2)

    def adjust_grid_for_current_price(
        self,
        entry_price: float,
        position_size: float,
        current_price: float,
        min_profit_pct: float = 1.0
    ) -> List[GridOrder]:
        """Adjust grid orders based on current market price.

        Ensures all sell orders are above current price with minimum profit margin.

        Args:
            entry_price: Original entry price.
            position_size: Total position size in base currency.
            current_price: Current market price.
            min_profit_pct: Minimum profit percentage for any order.

        Returns:
            Adjusted list of GridOrder objects.
        """
        tp_levels = self.TP_LEVELS.copy()
        quantity_pcts = self.QUANTITY_PCTS

        # Calculate minimum acceptable price
        min_price = current_price * (1 + min_profit_pct / 100.0)

        # Adjust TP levels that would result in prices below minimum
        adjusted_tp_levels = []
        for tp_pct in tp_levels:
            calculated_price = entry_price * (1 + tp_pct / 100.0)
            if calculated_price < min_price:
                # Recalculate TP percentage to meet minimum price
                new_tp_pct = ((min_price / entry_price) - 1) * 100
                adjusted_tp_levels.append(new_tp_pct)
            else:
                adjusted_tp_levels.append(tp_pct)

        return self.generate_grid(entry_price, position_size, adjusted_tp_levels)

    def reset_counter(self) -> None:
        """Reset order counter (useful for testing)."""
        self._order_counter = 0
        logger.debug("Grid order counter reset")
