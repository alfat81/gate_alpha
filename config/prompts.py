ENTRY_ANALYSIS_PROMPT = """
Актив: {pair}, Цена: {price}, Δ24h: {change_24h}%, Объём: ${volume:,.0f}
ПРАВИЛА:
1. Для LONG: stop_loss ДОЛЖЕН быть < entry_price (минимум на 1-2%)
2. position_pct: строго 1.0-3.0%
Верни ТОЛЬКО JSON:
{{"entry_price":число,"stop_loss":число(<entry_price),"position_pct":число(1-3),"reason":"строка","confidence":0-1,"risk_score":1-10}}
"""