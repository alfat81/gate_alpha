# Gate Alpha Agent

Автономный торговый агент для Gate.io Alpha (testnet) с локальной LLM Qwen 2.5:7b через Ollama.

## ⚠️ Важно

- **ТОЛЬКО TESTNET**: Агент работает исключительно с тестовой сетью Gate.io
- Никаких реальных ордеров или withdrawal-разрешений не требуется
- Все ордера в demo-режиме только логируются

## Требования

- Python 3.11+
- Ollama с моделью `qwen2.5:7b`
- API ключи Gate.io testnet

## Установка

### 1. Установите зависимости

```bash
cd gate-alpha-agent
pip install -r requirements.txt
```

### 2. Настройте Ollama

```bash
# Установите Ollama: https://ollama.ai
# Скачайте модель qwen2.5:7b
ollama pull qwen2.5:7b

# Запустите Ollama сервер (если не запущен)
ollama serve
```

### 3. Настройте переменные окружения

```bash
# Скопируйте пример файла окружения
cp .env.example .env

# Отредактируйте .env и добавьте ваши testnet credentials
GATE_API_KEY=your_testnet_api_key
GATE_API_SECRET=your_testnet_api_secret
GATE_API_BASE_URL=https://fx-api-testnet.gateio.ws/api/v4
```

Получить testnet API ключи можно на: https://www.gate.io/alpha

## Структура проекта

```
gate-alpha-agent/
├── config/
│   ├── settings.py      # Pydantic модели конфигурации
│   └── prompts.py       # SYSTEM_PROMPT и JSON schema
├── llm/
│   └── ollama_client.py # Клиент для Ollama с retry и валидацией
├── core/
│   ├── scanner.py       # Сканер рынка: фильтр по объёму, изменению, спреду
│   ├── risk_manager.py  # Валидация решений: position, stop-loss, risk score
│   ├── grid_manager.py  # Генерация сетки лимит-ордеров (5 уровней)
│   ├── agent.py         # Оркестратор: scan → LLM → risk → grid
│   └── models.py        # Pydantic модели для LLM ответов
├── gate_api/
│   └── testnet_client.py # Обёртка над gate-api SDK для testnet
├── tests/
│   └── test_integration.py # Интеграционные тесты
├── main.py              # Точка входа
├── requirements.txt     # Зависимости
├── .env.example         # Пример конфига
└── README.md
```

## Запуск

### Демо-режим (3 итерации)

```bash
python main.py
```

Агент выполнит 3 цикла сканирования рынка с интервалом 300 секунд (настраивается в `.env`).

### Запуск тестов

```bash
pytest tests/ -v
```

## Компоненты

### 1. Market Scanner (`core/scanner.py`)

Фильтрует тикеры по критериям:
- `|change_24h| > 15%`
- `volume_usd: 100K – 5M`
- `spread < 2%`

Возвращает top-N тикеров (по умолчанию 10).

### 2. LLM Client (`llm/ollama_client.py`)

- Метод `query_structured(prompt, schema)` с `temperature=0.15`
- Использует `format=json_schema` для строгого JSON
- Retry до 3 раз при ошибках
- Валидация ответов через Pydantic

### 3. Risk Manager (`core/risk_manager.py`)

Проверяет:
- `max_position_pct <= 3%`
- `stop_loss < entry_price`
- `risk_score <= 8`
- `daily_loss < 15%`
- `confidence >= 0.5`

Возвращает `(bool, reason)`.

### 4. Grid Manager (`core/grid_manager.py`)

Генерирует 5 лимит-ордеров на продажу:
- TP уровни: `[8%, 15%, 25%, 40%, 60%]`
- Распределение объёма: `[25%, 25%, 20%, 15%, 15%]`

### 5. Trading Agent (`core/agent.py`)

Оркестрирует цикл:
1. Scan market → получить тикеры
2. LLM analysis → получить решение
3. Risk validate → проверить риски
4. Create test order → (demo mode: логирование)
5. Place grid → (demo mode: логирование)

Асинхронный цикл с `sleep(300)` между итерациями.

## Конфигурация

Все настройки в `.env`:

```ini
# Gate.io API
GATE_API_KEY=your_key
GATE_API_SECRET=your_secret
GATE_API_BASE_URL=https://fx-api-testnet.gateio.ws/api/v4

# LLM
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Trading
MAX_POSITION_PCT=3.0
STOP_LOSS_PCT=5.0
MAX_RISK_SCORE=8
MAX_DAILY_LOSS_PCT=15.0
SCAN_INTERVAL_SECONDS=300

# Scanner
MIN_VOLUME_USD=100000
MAX_VOLUME_USD=5000000
MIN_CHANGE_24H_PCT=15.0
MAX_SPREAD_PCT=2.0
TOP_N_TICKERS=10
```

## Логирование

Используется `structlog` с уровнями INFO/ERROR:
- API ключи маскируются
- Все внешние вызовы логируются
- Ошибки валидации LLM логируются с деталями

## Безопасность

- 🔒 Только testnet URL
- 🔒 API ключи никогда не логируются полностью
- 🔒 Все внешние вызовы обернуты в try/except
- 🔒 Graceful shutdown при SIGINT/SIGTERM

## Разработка

### Добавить новые критерии сканера

Отредактируйте `core/scanner.py`, метод `_matches_criteria()`.

### Изменить TP уровни

Отредактируйте `core/grid_manager.py`, константы `TP_LEVELS` и `QUANTITY_PCTS`.

### Настроить LLM prompt

Отредактируйте `config/prompts.py`, переменные `SYSTEM_PROMPT` и `ANALYSIS_SCHEMA`.

## Лицензия

MIT
