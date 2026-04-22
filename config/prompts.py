# -*- coding: utf-8 -*-
ENTRY_ANALYSIS_PROMPT = """
Данные актива:
- Пара: {pair}
- Цена: {price} USDT
- Δ24h: {change_24h}%
- Объём: {volume} USDT

Верни строго JSON:
{{
  "entry_price": float,
  "stop_loss": float,
  "position_pct": float,
  "reason": "string",
  "confidence": float,
  "risk_score": int
}}
"""