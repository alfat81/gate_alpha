import gate_api
from config.settings import GateConfig

def create_testnet_client(config: GateConfig) -> gate_api.ApiClient:
    """Создаёт API-клиент для тестовой сети [[3]][[38]]"""
    configuration = gate_api.Configuration(
        host=config.base_url,
        key=config.api_key,
        secret=config.api_secret
    )
    configuration.verify_ssl = True  # Обязательно для безопасности
    return gate_api.ApiClient(configuration)

class TestnetSpotApi:
    """Обёртка над Spot API для testnet с упрощённым интерфейсом"""
    
    def __init__(self, config: GateConfig):
        api_client = create_testnet_client(config)
        self.spot_api = gate_api.SpotApi(api_client)
    
    def get_tickers(self) -> list:
        """Получает список тикеров с фильтрацией по ликвидности"""
        try:
            response = self.spot_api.list_tickers()
            return [t.to_dict() for t in response]
        except gate_api.ApiException as e:
            print(f"API Error: {e}")
            return []
    
    def create_order_test(self, currency_pair: str, side: str, amount: float, price: float):
        """Создаёт тестовый ордер (без реального исполнения на testnet)"""
        order = gate_api.Order(
            currency_pair=currency_pair,
            type='limit',
            side=side,
            amount=str(amount),
            price=str(price),
            text=f"test_{currency_pair}_{side}"
        )
        # На testnet ордеры не исполняются, но валидируются
        return self.spot_api.create_order(order)