import pytest
from config.settings import GateConfig, TradingConfig
from gate_api.testnet_client import TestnetSpotApi
from core.scanner import AlphaScanner

@pytest.fixture
def testnet_config():
    return GateConfig.testnet()

@pytest.fixture
def scanner(testnet_config):
    return AlphaScanner(config=testnet_config)

@pytest.mark.integration
@pytest.mark.testnet
def test_scan_alpha_opportunities(scanner):
    """Тест сканирования Alpha-секции на testnet"""
    opportunities = scanner.find_high_risk_pairs(limit=10)
    
    assert isinstance(opportunities, list)
    # На testnet данные могут быть ограничены
    if opportunities:
        pair = opportunities[0]
        assert 'currency_pair' in pair
        assert 'last' in pair  # цена

@pytest.mark.integration
@pytest.mark.testnet
def test_create_test_order(testnet_config):
    """Тест создания ордера на testnet (не исполняется)"""
    api = TestnetSpotApi(testnet_config)
    
    # Тестовая пара (должна существовать на testnet)
    result = api.create_order_test(
        currency_pair='BTC_USDT',
        side='buy',
        amount=0.001,
        price=10000  # Заведомо низкая цена для теста
    )
    
    # На testnet ожидаем валидацию, а не исполнение
    assert result is not None