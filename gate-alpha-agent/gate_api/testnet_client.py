"""Gate.io Testnet API client wrapper."""

from typing import Any

import structlog
from gate_api import ApiClient, Configuration, ApiException, SpotApi

from config.settings import GateConfig

logger = structlog.get_logger(__name__)


class GateTestnetClient:
    """Wrapper around gate-api SDK for testnet operations."""

    def __init__(self, config: GateConfig):
        """Initialize Gate.io testnet client.

        Args:
            config: Gate.io API configuration with credentials and base URL.
        """
        self.config = config
        self._api_client: ApiClient | None = None
        self._spot_api: SpotApi | None = None

    def _get_api_client(self) -> ApiClient:
        """Get or create API client instance.

        Returns:
            Configured ApiClient instance.
        """
        if self._api_client is None:
            configuration = Configuration()
            configuration.host = self.config.base_url
            configuration.key = self.config.api_key
            configuration.secret = self.config.api_secret

            # Set timeouts
            configuration.timeout = 30000  # 30 seconds in milliseconds

            self._api_client = ApiClient(configuration)
            logger.info(
                "Gate API client initialized",
                base_url=self._mask_url(self.config.base_url),
                api_key_prefix=self._mask_key(self.config.api_key)
            )

        return self._api_client

    def _get_spot_api(self) -> SpotApi:
        """Get or create Spot API instance.

        Returns:
            Configured SpotApi instance.
        """
        if self._spot_api is None:
            api_client = self._get_api_client()
            self._spot_api = SpotApi(api_client)
        return self._spot_api

    async def get_tickers(self) -> list[dict[str, Any]]:
        """Fetch all tickers from Gate.io.

        Returns:
            List of ticker dictionaries.

        Raises:
            ApiException: If API request fails.
            TimeoutError: If request times out.
        """
        try:
            spot_api = self._get_spot_api()
            tickers = spot_api.list_tickers()
            logger.debug("Fetched tickers", count=len(tickers))
            return tickers
        except ApiException as ae:
            logger.error("Gate API error fetching tickers", status=ae.status, reason=ae.reason)
            raise
        except TimeoutError as te:
            logger.error("Timeout fetching tickers")
            raise te

    async def get_account_balance(self) -> dict[str, float]:
        """Fetch account balance.

        Returns:
            Dictionary of currency -> balance.

        Raises:
            ApiException: If API request fails.
        """
        try:
            spot_api = self._get_spot_api()
            accounts = spot_api.list_spot_accounts()
            balance = {}
            for account in accounts:
                currency = account.currency
                available = float(account.available) if account.available else 0.0
                if available > 0:
                    balance[currency] = available
            logger.debug("Fetched account balance", currencies=list(balance.keys()))
            return balance
        except ApiException as ae:
            logger.error("Gate API error fetching balance", status=ae.status, reason=ae.reason)
            raise

    async def create_order(
        self,
        currency_pair: str,
        side: str,
        amount: float,
        price: float | None = None,
        order_type: str = "limit"
    ) -> dict[str, Any]:
        """Create a spot order.

        Args:
            currency_pair: Trading pair (e.g., 'BTC_USDT').
            side: 'buy' or 'sell'.
            amount: Order amount in base currency.
            price: Order price (required for limit orders).
            order_type: 'limit' or 'market'.

        Returns:
            Order response dictionary.

        Raises:
            ApiException: If API request fails.
        """
        try:
            spot_api = self._get_spot_api()

            order_params = {
                "currency_pair": currency_pair,
                "side": side,
                "amount": str(amount),
                "type": order_type
            }

            if order_type == "limit" and price is not None:
                order_params["price"] = str(price)

            logger.info(
                "Creating order",
                currency_pair=currency_pair,
                side=side,
                amount=amount,
                price=price,
                type=order_type
            )

            order = spot_api.create_order(order_params)
            logger.info(
                "Order created",
                order_id=order.id,
                status=order.status
            )
            return order
        except ApiException as ae:
            logger.error(
                "Gate API error creating order",
                status=ae.status,
                reason=ae.reason,
                currency_pair=currency_pair
            )
            raise

    async def cancel_order(self, order_id: str, currency_pair: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: Order ID to cancel.
            currency_pair: Trading pair.

        Returns:
            True if cancelled successfully.

        Raises:
            ApiException: If API request fails.
        """
        try:
            spot_api = self._get_spot_api()
            spot_api.cancel_order(order_id, currency_pair)
            logger.info("Order cancelled", order_id=order_id, currency_pair=currency_pair)
            return True
        except ApiException as ae:
            logger.error(
                "Gate API error cancelling order",
                status=ae.status,
                reason=ae.reason,
                order_id=order_id
            )
            raise

    async def get_order(self, order_id: str, currency_pair: str) -> dict[str, Any]:
        """Get order details.

        Args:
            order_id: Order ID.
            currency_pair: Trading pair.

        Returns:
            Order details dictionary.

        Raises:
            ApiException: If API request fails.
        """
        try:
            spot_api = self._get_spot_api()
            order = spot_api.get_order(order_id, currency_pair)
            return order
        except ApiException as ae:
            logger.error(
                "Gate API error fetching order",
                status=ae.status,
                reason=ae.reason,
                order_id=order_id
            )
            raise

    async def close(self) -> None:
        """Close the API client connection."""
        if self._api_client:
            self._api_client.close()
            self._api_client = None
            self._spot_api = None
            logger.info("Gate API client closed")

    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask sensitive parts of URL for logging."""
        if "testnet" in url:
            return url
        parts = url.split("//")
        if len(parts) == 2:
            return f"{parts[0]}//***REDACTED***"
        return "***REDACTED***"

    @staticmethod
    def _mask_key(key: str) -> str:
        """Mask API key for logging."""
        if not key:
            return "***EMPTY***"
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"
