"""Main trading agent orchestrator."""

import asyncio
from typing import Any

import structlog

from config.settings import Settings, GateConfig, TradingConfig, LLMConfig
from config.prompts import USER_PROMPT_TEMPLATE
from llm.ollama_client import OllamaClient
from core.scanner import MarketScanner, TickerData
from core.risk_manager import RiskManager, LLMAnalysis, RiskValidationResult
from core.grid_manager import GridManager, GridOrder
from core.models import LLMAnalysisModel
from gate_api.testnet_client import GateTestnetClient

logger = structlog.get_logger(__name__)


class TradingAgent:
    """Autonomous trading agent orchestrator."""

    def __init__(self, settings: Settings):
        """Initialize trading agent.

        Args:
            settings: Application settings container.
        """
        self.settings = settings
        self.gate_config = settings.gate
        self.trading_config = settings.trading
        self.llm_config = settings.llm

        # Initialize components
        self.scanner = MarketScanner(self.gate_config, self.trading_config)
        self.risk_manager = RiskManager(self.trading_config)
        self.grid_manager = GridManager()
        self.llm_client = OllamaClient(self.llm_config)
        self.gate_client = GateTestnetClient(self.gate_config)

        # State tracking
        self._is_running = False
        self._trades_executed = 0
        self._scan_count = 0

    async def start(self, demo_mode: bool = True, max_iterations: int | None = None) -> None:
        """Start the trading agent loop.

        Args:
            demo_mode: If True, skip actual order placement (test/demo mode).
            max_iterations: Maximum number of iterations (None for infinite).
        """
        self._is_running = True
        iteration = 0

        logger.info(
            "Trading agent started",
            demo_mode=demo_mode,
            max_iterations=max_iterations,
            scan_interval=self.trading_config.scan_interval_seconds
        )

        try:
            while self._is_running:
                iteration += 1
                logger.info("Starting iteration", iteration=iteration)

                await self._run_cycle(demo_mode=demo_mode)

                self._scan_count += 1

                # Check if we've reached max iterations
                if max_iterations and iteration >= max_iterations:
                    logger.info("Reached max iterations, stopping")
                    break

                # Wait for next scan interval
                logger.debug(
                    "Waiting for next scan interval",
                    seconds=self.trading_config.scan_interval_seconds
                )
                await asyncio.sleep(self.trading_config.scan_interval_seconds)

        except asyncio.CancelledError:
            logger.info("Agent loop cancelled")
        finally:
            await self.shutdown()

    async def _run_cycle(self, demo_mode: bool = True) -> None:
        """Run a single trading cycle.

        Args:
            demo_mode: If True, skip actual order placement.
        """
        # Step 1: Scan market for opportunities
        tickers = await self.scanner.scan()
        if not tickers:
            logger.info("No tickers matched scan criteria")
            return

        logger.info("Found matching tickers", count=len(tickers))

        # Step 2-6: Process each ticker
        for ticker in tickers:
            success = await self._process_ticker(ticker, demo_mode)
            if success:
                self._trades_executed += 1
                # Only process one trade per cycle
                break

    async def _process_ticker(self, ticker: TickerData, demo_mode: bool) -> bool:
        """Process a single ticker through the full pipeline.

        Args:
            ticker: Ticker data to process.
            demo_mode: If True, skip actual order placement.

        Returns:
            True if trade was successfully executed, False otherwise.
        """
        logger.info("Processing ticker", ticker=ticker.ticker, price=ticker.price)

        # Step 2: Get LLM analysis
        analysis = await self._get_llm_analysis(ticker)
        if analysis is None:
            logger.warning("Failed to get LLM analysis", ticker=ticker.ticker)
            return False

        # Convert to LLMAnalysis NamedTuple for risk manager
        llm_analysis = LLMAnalysis(
            must_trade=analysis.must_trade,
            confidence=analysis.confidence,
            reason=analysis.reason,
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            take_profit_levels=analysis.take_profit_levels,
            risk_score=analysis.risk_score,
            position_size_pct=analysis.position_size_pct
        )

        # Step 3: Validate with risk manager
        validation = self.risk_manager.validate(llm_analysis, ticker.price)
        if not validation.is_valid:
            logger.warning(
                "Risk validation failed",
                ticker=ticker.ticker,
                reason=validation.reason
            )
            return False

        logger.info(
            "Risk validation passed",
            ticker=ticker.ticker,
            risk_score=validation.risk_score
        )

        # Step 4: Create test order (demo mode only logs)
        if demo_mode:
            logger.info(
                "[DEMO MODE] Would create test order",
                ticker=ticker.ticker,
                entry_price=llm_analysis.entry_price,
                position_size_pct=llm_analysis.position_size_pct
            )
        else:
            # In production mode, would create actual test order here
            pass

        # Step 5: Generate and place grid orders
        # Calculate position size based on portfolio (assuming $10000 test portfolio)
        test_portfolio_value = 10000.0
        position_value = test_portfolio_value * (llm_analysis.position_size_pct / 100.0)
        position_size_base = position_value / llm_analysis.entry_price

        grid_orders = self.grid_manager.generate_grid(
            entry_price=llm_analysis.entry_price,
            position_size=position_size_base
        )

        # Step 6: Place grid orders
        if demo_mode:
            logger.info(
                "[DEMO MODE] Would place grid orders",
                ticker=ticker.ticker,
                num_orders=len(grid_orders),
                orders=[
                    {"tp_pct": o.take_profit_pct, "price": o.price, "qty": o.quantity}
                    for o in grid_orders
                ]
            )
        else:
            # In production mode, would place actual orders
            pass

        logger.info(
            "Ticker processing complete",
            ticker=ticker.ticker,
            grid_orders=len(grid_orders)
        )

        return True

    async def _get_llm_analysis(self, ticker: TickerData) -> LLMAnalysisModel | None:
        """Get LLM analysis for a ticker.

        Args:
            ticker: Ticker data to analyze.

        Returns:
            Validated LLM analysis or None if failed.
        """
        # Determine market condition based on change
        if abs(ticker.change_24h_pct) > 30:
            market_condition = "extreme"
        elif abs(ticker.change_24h_pct) > 20:
            market_condition = "high"
        else:
            market_condition = "moderate"

        # Determine session type (simplified)
        session_type = "active"

        # Build user prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            ticker=ticker.ticker,
            price=ticker.price,
            change_24h=ticker.change_24h_pct,
            volume_usd=ticker.volume_usd,
            bid=ticker.bid,
            ask=ticker.ask,
            spread=ticker.spread_pct,
            market_condition=market_condition,
            session_type=session_type
        )

        # Query LLM
        analysis = await self.llm_client.query_structured(
            prompt=user_prompt,
            response_model=LLMAnalysisModel
        )

        return analysis

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent."""
        logger.info("Shutting down trading agent")
        self._is_running = False

        # Close all clients
        await self.llm_client.close()
        await self.scanner.close()
        await self.gate_client.close()

        logger.info(
            "Agent shutdown complete",
            total_scans=self._scan_count,
            trades_executed=self._trades_executed
        )

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Dictionary of agent statistics.
        """
        return {
            "is_running": self._is_running,
            "scan_count": self._scan_count,
            "trades_executed": self._trades_executed
        }
