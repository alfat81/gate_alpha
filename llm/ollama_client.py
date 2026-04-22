import json
from typing import Type, TypeVar
from pydantic import BaseModel
import ollama
from config.settings import LLMConfig

T = TypeVar('T', bound=BaseModel)

class OllamaClient:
    """Клиент для работы с локальной LLM через Ollama"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = ollama.Client(host=config.host)
    
    def query_structured(self, prompt: str, response_model: Type[T]) -> T:
        """
        Запрос к LLM со структурированным выводом [[47]][[50]]
        
        Args:
            prompt: Текст запроса
            response_model: Pydantic-модель ожидаемого ответа
            
        Returns:
            Распарсенный объект модели
        """
        schema = response_model.model_json_schema()
        
        response = self.client.chat(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            format=schema,  # Принудительный JSON-формат
            options={"temperature": self.config.temperature}
        )
        
        content = response['message']['content']
        return response_model.model_validate_json(content)
def query_structured(self, prompt: str, response_model: Type[T]) -> T:
    schema = response_model.model_json_schema()
    response = self.client.chat(
        model=self.config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        format=schema,  # Pydantic schema → Ollama автоматически валидирует
        options={"temperature": self.config.temperature}
    )
    return response_model.model_validate_json(response["message"]["content"])