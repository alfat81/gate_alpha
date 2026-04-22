SYSTEM_PROMPT = """Ты — алгоритмический криптотрейдер. Анализируешь только предоставленные данные. 
Всегда возвращай валидный JSON без пояснений, markdown-обёрток или комментариев."""

ENTRY_ANALYSIS_PROMPT = """
Данные актива:
- Пара: {symbol}
- Цена: {price} USDT
- Δ24h: {change_24h}%
- Объём: {volume_usd} USDT

Верни строго JSON:
{{
  "entry_price": float,
  "stop_loss": float,
  "position_pct": float,
  "reason": "string",
  "confidence": float (0.0-1.0),
  "risk_score": int (1-10)
}}
"""

GRID_EXIT_PROMPT = """
Вход: {entry_price}, Позиция: {position_size}, Волатильность: {volatility}%
Сгенерируй сетку выхода (5 уровней ТП, распределение 25/25/20/15/15%).
Верни строго JSON-массив объектов: {{"price": float, "amount_pct": int, "text": string}}
"""