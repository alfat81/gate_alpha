# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Type, TypeVar
from pydantic import BaseModel
import ollama
from config.settings import LLMConfig

logger = logging.getLogger(__name__)
T = TypeVar('T', bound=BaseModel)

class OllamaClient:
    """Асинхронный клиент для структурированного вывода Ollama с ретраями."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = ollama.AsyncClient(host=config.host)
    
    async def query_structured(self, prompt: str, response_model: Type[T]) -> T:
        """
        Запрос к LLM с гарантированным JSON-ответом.
        Включает 3 попытки, таймаут и очистку от markdown.
        """
        schema = response_model.model_json_schema()
        
        # Параметры генерации
        options = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "num_predict": self.config.num_predict,
        }
        
        messages = [
            {"role": "system", "content": "Отвечай ТОЛЬКО валидным JSON. Без markdown, без ```."},
            {"role": "user", "content": prompt}
        ]
        
        last_error = None
        
        # Цикл ретраев (3 попытки)
        for attempt in range(3):
            try:
                # 🔥 Асинхронный вызов с таймаутом
                response = await asyncio.wait_for(
                    self.client.chat(
                        model=self.config.model,
                        messages=messages,
                        format=schema,
                        options=options
                    ),
                    timeout=self.config.timeout
                )
                
                content = response['message']['content'].strip()
                
                # 🔥 Очистка от markdown-обёрток (если модель всё же их добавила)
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # Валидация через Pydantic
                return response_model.model_validate_json(content)
                
            except asyncio.TimeoutError:
                last_error = f"Таймаут {self.config.timeout}с (попытка {attempt+1}/3)"
                logger.warning(last_error)
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная пауза
                
            except Exception as e:
                last_error = f"Ошибка: {e} (попытка {attempt+1}/3)"
                logger.warning(last_error)
                await asyncio.sleep(1)
        
        # 🔥 Если все попытки исчерпаны
        raise RuntimeError(f"Не удалось получить ответ от LLM. Последняя ошибка: {last_error}")