# -*- coding: utf-8 -*-
import logging
from typing import Type, TypeVar
from pydantic import BaseModel
import ollama
from config.settings import LLMConfig

logger = logging.getLogger(__name__)
T = TypeVar('T', bound=BaseModel)

class OllamaClient:
    """Асинхронный клиент для структурированного вывода Ollama."""
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = ollama.AsyncClient(host=config.host)

    async def query_structured(self, prompt: str, response_model: Type[T]) -> T:
        schema = response_model.model_json_schema()
        try:
            response = await self.client.chat(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "Отвечай строго валидным JSON. Без markdown, без пояснений."},
                    {"role": "user", "content": prompt}
                ],
                format=schema,
                options={"temperature": self.config.temperature}
            )
            content = response['message']['content']
            return response_model.model_validate_json(content)
        except Exception as e:
            logger.error(f"Ошибка запроса к Ollama: {e}")
            raise