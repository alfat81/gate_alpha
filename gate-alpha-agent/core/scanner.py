"""Market scanner for finding trading opportunities."""

from typing import NamedTuple

import structlog
from gate_api import ApiException

from config.settings import TradingConfig, GateConfig
from gate_api.testnet_client import GateTestnetClient

logger = structlog.get_logger(__name__)


class TickerData(NamedTuple):
    """Ticker data container."""

    ticker: str
    price: float
    change_24h_pct: float
    volume_usd: float
    bid: float
    ask: float
    spread_pct: float


class MarketScanner:
    """Scans market for trading opportunities based on configured criteria."""

    def __init__(self, gate_config: GateConfig, trading_config: TradingConfig):
        """Initialize market scanner.

        Args:
            gate_config: Gate.io API configuration.
            trading_config: Trading configuration with filter criteria.
        """
        self.gate_config = gate_config
        self.trading_config = trading_config
        self.client = GateTestnetClient(gate_config)

    async def scan(self) -> list[TickerData]:
        """Scan market and return tickers matching filter criteria.

        Returns:
            List of TickerData objects matching the filter criteria, sorted by |change_24h|.
        """
        try:
            tickers = await self.client.get_tickers()
        except ApiException as ae:
            logger.error("Failed to fetch tickers from Gate.io", error=str(ae))
            return []
        except TimeoutError as te:
            logger.error("Timeout fetching tickers", error=str(te))
            return []
        except Exception as e:
            logger.error("Unexpected error fetching tickers", error=str(e))
            return []

        filtered = []

        for ticker in tickers:
            try:
                ticker_data = self._process_ticker(ticker)
                if ticker_data and self._matches_criteria(ticker_data):
                    filtered.append(ticker_data)
            except (ValueError, KeyError, TypeError) as e:
                logger.debug(
                    "Skipping malformed ticker data",
                    ticker=ticker.get("currency_pair", "unknown"),
                    error=str(e)
                )
                continue

        # Sort by absolute 24h change descending and take top N
        filtered.sort(key=lambda x: abs(x.change_24h_pct), reverse=True)
        result = filtered[:self.trading_config.top_n_tickers]

        logger.info(
            "Scan completed",
            total_tickers=len(tickers),
            filtered_count=len(filtered),
            returned_count=len(result)
        )

        return result

    def _process_ticker(self, ticker: dict) -> TickerData | None:
        """Process raw ticker data into TickerData.

        Args:
            ticker: Raw ticker dictionary from Gate API.

        Returns:
            TickerData object or None if data is invalid.
        """
        currency_pair = ticker.get("currency_pair", "")
        last_price = float(ticker.get("last", 0))
        change_pct = float(ticker.get("change_percentage", 0))
        volume_24h = float(ticker.get("volume_24h", 0))
        quote_volume = float(ticker.get("quote_volume_24h", 0))

        # Calculate USD volume (quote_volume is already in quote currency)
        # For USDT pairs, this is already USD equivalent
        volume_usd = quote_volume

        bid = float(ticker.get("highest_bid", 0))
        ask = float(ticker.get("lowest_ask", 0))

        # Calculate spread percentage
        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / bid) * 100
        else:
            spread_pct = 100.0  # Invalid spread

        return TickerData(
            ticker=currency_pair,
            price=last_price,
            change_24h_pct=change_pct,
            volume_usd=volume_usd,
            bid=bid,
            ask=ask,
            spread_pct=spread_pct
        )

    def _matches_criteria(self, ticker: TickerData) -> bool:
        """Check if ticker matches filter criteria.

        Args:
            ticker: TickerData to check.

        Returns:
            True if ticker matches all criteria, False otherwise.
        """
        # Check |change_24h| > threshold
        if abs(ticker.change_24h_pct) < self.trading_config.min_change_24h_pct:
            return False

        # Check volume range
        if ticker.volume_usd < self.trading_config.min_volume_usd:
            return False
        if ticker.volume_usd > self.trading_config.max_volume_usd:
            return False

        # Check spread
        if ticker.spread_pct > self.trading_config.max_spread_pct:
            return False

        # Check valid prices
        if ticker.price <= 0 or ticker.bid <= 0 or ticker.ask <= 0:
            return False

        return True

    async def close(self) -> None:
        """Close scanner resources."""
        await self.client.close()
