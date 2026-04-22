"""Main entry point for Gate Alpha Agent."""

import asyncio
import logging
import signal
import sys

import structlog
from dotenv import load_dotenv

from config.settings import Settings
from core.agent import TradingAgent
from llm.ollama_client import OllamaClient

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger(__name__)


class GracefulShutdown:
    """Handle graceful shutdown on SIGINT/SIGTERM."""

    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self._agent: TradingAgent | None = None

    def register_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal)

    def _handle_signal(self):
        """Handle shutdown signal."""
        logger.warning("Shutdown signal received")
        self.shutdown_event.set()

    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()

    def set_agent(self, agent: TradingAgent):
        """Set the agent reference for shutdown."""
        self._agent = agent


async def check_ollama_health(llm_config) -> bool:
    """Check if Ollama is running and model is available.

    Args:
        llm_config: LLM configuration.

    Returns:
        True if healthy, False otherwise.
    """
    client = OllamaClient(llm_config)
    try:
        is_healthy = await client.health_check()
        await client.close()
        return is_healthy
    except Exception as e:
        logger.error("Failed to check Ollama health", error=str(e))
        return False


async def run_demo_cycle(settings: Settings, iterations: int = 3):
    """Run demo cycle with specified number of iterations.

    Args:
        settings: Application settings.
        iterations: Number of demo iterations to run.
    """
    logger.info(
        "Starting demo cycle",
        iterations=iterations,
        scan_interval=settings.trading.scan_interval_seconds
    )

    agent = TradingAgent(settings)
    shutdown = GracefulShutdown()
    shutdown.set_agent(agent)
    shutdown.register_signal_handlers()

    # Create task for agent
    agent_task = asyncio.create_task(
        agent.start(demo_mode=True, max_iterations=iterations)
    )

    # Wait for either shutdown signal or agent completion
    done, pending = await asyncio.wait(
        [agent_task, asyncio.create_task(shutdown.wait_for_shutdown())],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Cancel pending tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("Demo cycle completed", stats=agent.get_stats())


async def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    logger.info("Gate Alpha Agent starting...")

    # Load settings
    settings = Settings.load()
    logger.info(
        "Settings loaded",
        gate_url=settings.gate.base_url,
        llm_model=settings.llm.model,
        demo_mode=True
    )

    # Check Ollama health
    logger.info("Checking Ollama health...")
    ollama_healthy = await check_ollama_health(settings.llm)

    if not ollama_healthy:
        logger.error(
            "Ollama is not healthy or model not available. "
            "Please ensure Ollama is running and qwen2.5:7b is pulled."
        )
        logger.error("Run: ollama pull qwen2.5:7b")
        sys.exit(1)

    logger.info("Ollama health check passed")

    # Run demo cycle (3 iterations for testing)
    await run_demo_cycle(settings, iterations=3)

    logger.info("Gate Alpha Agent stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception("Fatal error", error=str(e))
        sys.exit(1)
