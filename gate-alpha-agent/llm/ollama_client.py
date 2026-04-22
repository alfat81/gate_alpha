"""Ollama LLM client for structured JSON responses."""

import asyncio
import json
from typing import Any, Type, TypeVar

import structlog
from ollama import AsyncClient, ResponseError
from pydantic import BaseModel, ValidationError

from config.settings import LLMConfig
from config.prompts import SYSTEM_PROMPT, ANALYSIS_SCHEMA

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    """Async Ollama client for structured LLM queries."""

    def __init__(self, config: LLMConfig):
        """Initialize Ollama client.

        Args:
            config: LLM configuration with host, model, and parameters.
        """
        self.config = config
        self.client = AsyncClient(host=config.host)
        self._model = config.model
        self._temperature = config.temperature
        self._max_retries = config.max_retries

    async def health_check(self) -> bool:
        """Check if Ollama server is running and model is available.

        Returns:
            True if server is healthy and model is ready, False otherwise.
        """
        try:
            response = await self.client.list()
            models = [m["name"] for m in response.get("models", [])]
            if self._model in models:
                logger.info("Ollama health check passed", model=self._model)
                return True
            else:
                logger.warning(
                    "Model not found in Ollama",
                    model=self._model,
                    available_models=models
                )
                return False
        except (ResponseError, ConnectionError, TimeoutError) as e:
            logger.error("Ollama health check failed", error=str(e))
            return False

    async def query_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: str = SYSTEM_PROMPT
    ) -> T | None:
        """Query LLM with structured JSON output validation.

        Args:
            prompt: User prompt for the LLM.
            response_model: Pydantic model to validate the response against.
            system_prompt: System prompt to guide the LLM behavior.

        Returns:
            Validated Pydantic model instance or None if validation fails after retries.
        """
        last_error = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.debug(
                    "Querying LLM",
                    attempt=attempt,
                    max_retries=self._max_retries,
                    model=self._model
                )

                response = await self.client.chat(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    format=ANALYSIS_SCHEMA,
                    options={
                        "temperature": self._temperature,
                        "num_predict": 512
                    }
                )

                content = response["message"]["content"]
                logger.debug("Raw LLM response received", content_preview=content[:200])

                # Parse JSON from response
                try:
                    parsed_data = json.loads(content)
                except json.JSONDecodeError as je:
                    logger.warning(
                        "Failed to parse JSON from LLM response",
                        error=str(je),
                        content=content
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.5 * attempt)
                        continue
                    return None

                # Validate against Pydantic model
                try:
                    validated = response_model.model_validate(parsed_data)
                    logger.info(
                        "LLM response validated successfully",
                        model=response_model.__name__,
                        must_trade=validated.must_trade if hasattr(validated, 'must_trade') else None
                    )
                    return validated
                except ValidationError as ve:
                    logger.warning(
                        "Pydantic validation failed",
                        errors=ve.errors(),
                        data=parsed_data
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.5 * attempt)
                        continue
                    return None

            except ResponseError as re:
                last_error = re
                logger.error(
                    "Ollama API error",
                    error=str(re),
                    attempt=attempt
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(1.0 * attempt)
                    continue
                return None

            except (ConnectionError, TimeoutError) as ce:
                last_error = ce
                logger.error(
                    "Connection error to Ollama",
                    error=str(ce),
                    attempt=attempt
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(1.0 * attempt)
                    continue
                return None

        logger.error(
            "All retry attempts exhausted",
            max_retries=self._max_retries,
            last_error=str(last_error) if last_error else "unknown"
        )
        return None

    async def close(self) -> None:
        """Close the Ollama client connection."""
        await self.client.close()
        logger.info("Ollama client closed")
