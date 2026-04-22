"""Integration tests for Gate Alpha Agent."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from config.settings import GateConfig, TradingConfig, LLMConfig, Settings
from core.scanner import MarketScanner, TickerData
from core.risk_manager import RiskManager, LLMAnalysis, RiskValidationResult
from core.grid_manager import GridManager, GridOrder
from core.models import LLMAnalysisModel


class TestMarketScanner:
    """Tests for MarketScanner."""

    @pytest.fixture
    def gate_config(self):
        return GateConfig(
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://fx-api-testnet.gateio.ws/api/v4"
        )

    @pytest.fixture
    def trading_config(self):
        return TradingConfig(
            min_change_24h_pct=15.0,
            min_volume_usd=100000.0,
            max_volume_usd=5000000.0,
            max_spread_pct=2.0,
            top_n_tickers=10
        )

    def test_matches_criteria_pass(self, gate_config, trading_config):
        """Test ticker matching all criteria."""
        scanner = MarketScanner(gate_config, trading_config)
        
        ticker = TickerData(
            ticker="BTC_USDT",
            price=50000.0,
            change_24h_pct=20.0,  # > 15%
            volume_usd=500000.0,  # in range
            bid=49990.0,
            ask=50010.0,
            spread_pct=0.04  # < 2%
        )
        
        assert scanner._matches_criteria(ticker) is True

    def test_matches_criteria_low_change(self, gate_config, trading_config):
        """Test ticker with low 24h change."""
        scanner = MarketScanner(gate_config, trading_config)
        
        ticker = TickerData(
            ticker="ETH_USDT",
            price=3000.0,
            change_24h_pct=10.0,  # < 15%
            volume_usd=500000.0,
            bid=2999.0,
            ask=3001.0,
            spread_pct=0.07
        )
        
        assert scanner._matches_criteria(ticker) is False

    def test_matches_criteria_high_spread(self, gate_config, trading_config):
        """Test ticker with high spread."""
        scanner = MarketScanner(gate_config, trading_config)
        
        ticker = TickerData(
            ticker="ALT_USDT",
            price=1.0,
            change_24h_pct=25.0,
            volume_usd=200000.0,
            bid=0.98,
            ask=1.02,
            spread_pct=4.08  # > 2%
        )
        
        assert scanner._matches_criteria(ticker) is False

    def test_matches_criteria_low_volume(self, gate_config, trading_config):
        """Test ticker with low volume."""
        scanner = MarketScanner(gate_config, trading_config)
        
        ticker = TickerData(
            ticker="LOW_VOL_USDT",
            price=10.0,
            change_24h_pct=30.0,
            volume_usd=50000.0,  # < 100K
            bid=9.99,
            ask=10.01,
            spread_pct=0.2
        )
        
        assert scanner._matches_criteria(ticker) is False


class TestRiskManager:
    """Tests for RiskManager."""

    @pytest.fixture
    def trading_config(self):
        return TradingConfig(
            max_position_pct=3.0,
            stop_loss_pct=5.0,
            max_risk_score=8,
            max_daily_loss_pct=15.0
        )

    @pytest.fixture
    def risk_manager(self, trading_config):
        return RiskManager(trading_config)

    def test_validate_pass(self, risk_manager):
        """Test valid analysis passes validation."""
        analysis = LLMAnalysis(
            must_trade=True,
            confidence=0.85,
            reason="Strong bullish signal",
            entry_price=100.0,
            stop_loss=95.0,  # 5% below entry
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=6,
            position_size_pct=2.5
        )
        
        result = risk_manager.validate(analysis, current_price=100.0)
        
        assert result.is_valid is True
        assert result.reason == "All risk checks passed"

    def test_validate_no_trade(self, risk_manager):
        """Test analysis with must_trade=False."""
        analysis = LLMAnalysis(
            must_trade=False,
            confidence=0.4,
            reason="Unclear signals",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=5,
            position_size_pct=1.0
        )
        
        result = risk_manager.validate(analysis, current_price=100.0)
        
        assert result.is_valid is False
        assert "LLM does not recommend trading" in result.reason

    def test_validate_position_too_large(self, risk_manager):
        """Test position size exceeds maximum."""
        analysis = LLMAnalysis(
            must_trade=True,
            confidence=0.9,
            reason="Great opportunity",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=5,
            position_size_pct=5.0  # > 3% max
        )
        
        result = risk_manager.validate(analysis, current_price=100.0)
        
        assert result.is_valid is False
        assert "exceeds max" in result.reason

    def test_validate_stop_loss_invalid(self, risk_manager):
        """Test stop loss >= entry price."""
        analysis = LLMAnalysis(
            must_trade=True,
            confidence=0.8,
            reason="Bullish",
            entry_price=100.0,
            stop_loss=100.0,  # Equal to entry (invalid)
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=5,
            position_size_pct=2.0
        )
        
        result = risk_manager.validate(analysis, current_price=100.0)
        
        assert result.is_valid is False
        assert "must be less than entry" in result.reason

    def test_validate_risk_score_too_high(self, risk_manager):
        """Test risk score exceeds maximum."""
        analysis = LLMAnalysis(
            must_trade=True,
            confidence=0.75,
            reason="High risk opportunity",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=9,  # > 8 max
            position_size_pct=2.0
        )
        
        result = risk_manager.validate(analysis, current_price=100.0)
        
        assert result.is_valid is False
        assert "exceeds maximum" in result.reason

    def test_validate_low_confidence(self, risk_manager):
        """Test low confidence level."""
        analysis = LLMAnalysis(
            must_trade=True,
            confidence=0.4,  # < 0.5 threshold
            reason="Uncertain",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=4,
            position_size_pct=2.0
        )
        
        result = risk_manager.validate(analysis, current_price=100.0)
        
        assert result.is_valid is False
        assert "below threshold" in result.reason


class TestGridManager:
    """Tests for GridManager."""

    @pytest.fixture
    def grid_manager(self):
        return GridManager()

    def test_generate_grid_default(self, grid_manager):
        """Test grid generation with default TP levels."""
        orders = grid_manager.generate_grid(
            entry_price=100.0,
            position_size=1.0
        )
        
        assert len(orders) == 5
        assert orders[0].take_profit_pct == 8.0
        assert orders[0].quantity_pct == 25.0
        assert orders[0].price == 108.0  # 100 * 1.08
        assert orders[0].quantity == 0.25  # 1.0 * 0.25

    def test_generate_grid_prices_increasing(self, grid_manager):
        """Test that TP prices are increasing."""
        orders = grid_manager.generate_grid(
            entry_price=100.0,
            position_size=1.0
        )
        
        prices = [o.price for o in orders]
        assert prices == sorted(prices)

    def test_generate_grid_quantity_sum(self, grid_manager):
        """Test total quantity equals position size."""
        orders = grid_manager.generate_grid(
            entry_price=100.0,
            position_size=10.0
        )
        
        total_qty = sum(o.quantity for o in orders)
        assert abs(total_qty - 10.0) < 0.0001

    def test_generate_grid_custom_levels(self, grid_manager):
        """Test grid with custom TP levels."""
        custom_tp = [10.0, 20.0, 30.0]
        orders = grid_manager.generate_grid(
            entry_price=100.0,
            position_size=1.0,
            custom_tp_levels=custom_tp
        )
        
        assert len(orders) == 3
        assert orders[0].take_profit_pct == 10.0
        assert orders[0].price == 110.0

    def test_calculate_total_value(self, grid_manager):
        """Test total value calculation."""
        orders = grid_manager.generate_grid(
            entry_price=100.0,
            position_size=1.0
        )
        
        prices = [o.price for o in orders]
        total_value = grid_manager.calculate_total_value(orders, prices)
        
        expected = sum(o.quantity * o.price for o in orders)
        assert abs(total_value - expected) < 0.01


class TestLLMAnalysisModel:
    """Tests for LLMAnalysisModel Pydantic validation."""

    def test_valid_model(self):
        """Test valid model creation."""
        model = LLMAnalysisModel(
            must_trade=True,
            confidence=0.85,
            reason="Test reason",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_levels=[108.0, 115.0, 125.0],
            risk_score=6,
            position_size_pct=2.5
        )
        
        assert model.must_trade is True
        assert model.confidence == 0.85
        assert len(model.take_profit_levels) == 3

    def test_invalid_confidence_high(self):
        """Test confidence > 1.0 fails."""
        with pytest.raises(ValidationError):
            LLMAnalysisModel(
                must_trade=True,
                confidence=1.5,  # Invalid
                reason="Test",
                entry_price=100.0,
                stop_loss=95.0,
                take_profit_levels=[108.0, 115.0, 125.0],
                risk_score=6,
                position_size_pct=2.5
            )

    def test_invalid_risk_score(self):
        """Test risk_score > 10 fails."""
        with pytest.raises(ValidationError):
            LLMAnalysisModel(
                must_trade=True,
                confidence=0.8,
                reason="Test",
                entry_price=100.0,
                stop_loss=95.0,
                take_profit_levels=[108.0, 115.0, 125.0],
                risk_score=11,  # Invalid
                position_size_pct=2.5
            )

    def test_invalid_position_size(self):
        """Test position_size > 100 fails."""
        with pytest.raises(ValidationError):
            LLMAnalysisModel(
                must_trade=True,
                confidence=0.8,
                reason="Test",
                entry_price=100.0,
                stop_loss=95.0,
                take_profit_levels=[108.0, 115.0, 125.0],
                risk_score=6,
                position_size_pct=150.0  # Invalid
            )

    def test_invalid_tp_levels_empty(self):
        """Test empty take_profit_levels fails."""
        with pytest.raises(ValidationError):
            LLMAnalysisModel(
                must_trade=True,
                confidence=0.8,
                reason="Test",
                entry_price=100.0,
                stop_loss=95.0,
                take_profit_levels=[],  # Invalid - too few
                risk_score=6,
                position_size_pct=2.5
            )


class TestIntegration:
    """Integration tests for the full pipeline."""

    @pytest.fixture
    def settings(self):
        return Settings(
            gate=GateConfig(api_key="test", api_secret="test"),
            llm=LLMConfig(),
            trading=TradingConfig()
        )

    @pytest.mark.asyncio
    async def test_scanner_mock_api(self, settings):
        """Test scanner with mocked API."""
        mock_tickers = [
            {
                "currency_pair": "BTC_USDT",
                "last": "50000.0",
                "change_percentage": "20.0",
                "quote_volume_24h": "500000.0",
                "highest_bid": "49990.0",
                "lowest_ask": "50010.0"
            }
        ]
        
        with patch('gate_api.testnet_client.GateTestnetClient.get_tickers', 
                   new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_tickers
            
            scanner = MarketScanner(settings.gate, settings.trading)
            tickers = await scanner.scan()
            
            assert len(tickers) > 0
            assert tickers[0].ticker == "BTC_USDT"
            await scanner.close()

    def test_full_pipeline_validation(self, settings):
        """Test full pipeline from analysis to grid."""
        # Create analysis
        analysis_model = LLMAnalysisModel(
            must_trade=True,
            confidence=0.85,
            reason="Strong signals",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_levels=[108.0, 115.0, 125.0, 140.0, 160.0],
            risk_score=6,
            position_size_pct=2.5
        )
        
        # Convert to NamedTuple for risk manager
        analysis = LLMAnalysis(
            must_trade=analysis_model.must_trade,
            confidence=analysis_model.confidence,
            reason=analysis_model.reason,
            entry_price=analysis_model.entry_price,
            stop_loss=analysis_model.stop_loss,
            take_profit_levels=analysis_model.take_profit_levels,
            risk_score=analysis_model.risk_score,
            position_size_pct=analysis_model.position_size_pct
        )
        
        # Validate
        risk_manager = RiskManager(settings.trading)
        validation = risk_manager.validate(analysis, current_price=100.0)
        assert validation.is_valid is True
        
        # Generate grid
        grid_manager = GridManager()
        position_size = 10000.0 * (analysis.position_size_pct / 100.0) / analysis.entry_price
        orders = grid_manager.generate_grid(analysis.entry_price, position_size)
        
        assert len(orders) == 5
        assert all(o.price > analysis.entry_price for o in orders)
