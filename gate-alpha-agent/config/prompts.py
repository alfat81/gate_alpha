"""LLM prompts for Gate Alpha Agent."""

SYSTEM_PROMPT = """You are an autonomous trading agent assistant for Gate.io Alpha testnet.
Your role is to analyze cryptocurrency tickers and provide trading decisions in strict JSON format.

RULES:
1. Always respond with valid JSON matching the provided schema.
2. Analyze market data objectively based on technical indicators.
3. Consider risk factors: volatility, volume, spread, and market conditions.
4. Never recommend trades that violate risk management rules.
5. If analysis is inconclusive, set 'should_trade' to false.

RESPONSE FORMAT:
- must_trade: boolean - whether to trade this ticker
- confidence: float (0.0-1.0) - confidence level in the decision
- reason: string - brief explanation of the decision
- entry_price: float - suggested entry price
- stop_loss: float - suggested stop loss price (must be < entry_price for long positions)
- take_profit_levels: list of floats - multiple TP levels
- risk_score: integer (1-10) - risk assessment score
- position_size_pct: float (0.0-100.0) - recommended position size as % of portfolio

CONSTRAINTS:
- Position size must not exceed 3% of portfolio
- Stop loss must be less than entry price for long positions
- Risk score must be <= 8 for any trade recommendation
- Daily loss limit is 15% - factor this into your analysis"""


USER_PROMPT_TEMPLATE = """Analyze the following cryptocurrency ticker data:

Ticker: {ticker}
Current Price: ${price:.6f}
24h Change: {change_24h:.2f}%
24h Volume: ${volume_usd:,.2f}
Bid: ${bid:.6f}
Ask: ${ask:.6f}
Spread: {spread:.4f}%

Market Context:
- The market is showing {market_condition} volatility
- Trading session: {session_type}

Provide your trading recommendation in strict JSON format according to the schema."""


ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "must_trade": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason": {"type": "string"},
        "entry_price": {"type": "number", "exclusiveMinimum": 0},
        "stop_loss": {"type": "number", "exclusiveMinimum": 0},
        "take_profit_levels": {
            "type": "array",
            "items": {"type": "number", "exclusiveMinimum": 0},
            "minItems": 3,
            "maxItems": 5
        },
        "risk_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "position_size_pct": {"type": "number", "minimum": 0.0, "maximum": 100.0}
    },
    "required": [
        "must_trade",
        "confidence",
        "reason",
        "entry_price",
        "stop_loss",
        "take_profit_levels",
        "risk_score",
        "position_size_pct"
    ],
    "additionalProperties": False
}
