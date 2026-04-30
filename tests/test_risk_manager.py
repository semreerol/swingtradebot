"""
Tests for risk manager and position sizer.
"""
import pytest
from app.risk.position_sizer import calculate_position_size
from app.risk.risk_manager import validate_signal, RiskResult
from app.strategies.base import StrategySignal


# ═══════════════════════════════════════════════════════════════════════════
# Position Sizer Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPositionSizer:
    """Tests for position size calculation."""

    def test_basic_position_size(self):
        """Basic quantity calculation should be correct."""
        # balance=10000, risk=1%, entry=100, sl=95
        # risk_amount = 100, price_risk = 5, qty = 20
        quantity, risk_amount = calculate_position_size(
            account_balance=10000,
            risk_per_trade=0.01,
            entry=100.0,
            stop_loss=95.0,
        )
        assert risk_amount == pytest.approx(100.0)
        assert quantity == pytest.approx(20.0)

    def test_position_size_btc(self):
        """BTC-like position sizing."""
        # balance=10000, risk=1%, entry=65000, sl=61800
        # risk_amount = 100, price_risk = 3200, qty = 0.03125
        quantity, risk_amount = calculate_position_size(
            account_balance=10000,
            risk_per_trade=0.01,
            entry=65000.0,
            stop_loss=61800.0,
        )
        assert risk_amount == pytest.approx(100.0)
        assert quantity == pytest.approx(100.0 / 3200.0)

    def test_stop_loss_above_entry_raises(self):
        """Should raise if stop-loss >= entry for LONG."""
        with pytest.raises(ValueError, match="less than entry"):
            calculate_position_size(
                account_balance=10000,
                risk_per_trade=0.01,
                entry=100.0,
                stop_loss=105.0,
            )

    def test_zero_balance_raises(self):
        """Should raise if account balance is zero."""
        with pytest.raises(ValueError, match="positive"):
            calculate_position_size(
                account_balance=0,
                risk_per_trade=0.01,
                entry=100.0,
                stop_loss=95.0,
            )

    def test_invalid_risk_raises(self):
        """Should raise if risk_per_trade is out of range."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            calculate_position_size(
                account_balance=10000,
                risk_per_trade=1.5,
                entry=100.0,
                stop_loss=95.0,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Risk Manager Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRiskManager:
    """Tests for risk manager validation."""

    def _make_signal(self, **kwargs) -> StrategySignal:
        """Helper to create a test signal."""
        defaults = {
            "has_signal": True,
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry": 65000.0,
            "stop_loss": 61800.0,
            "take_profit": 71400.0,
            "risk_reward": 2.0,
            "strategy_id": "test_strategy",
            "reason": ["test"],
        }
        defaults.update(kwargs)
        return StrategySignal(**defaults)

    def test_approved_signal(self):
        """Valid signal should be approved."""
        signal = self._make_signal()
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is True
        assert result.quantity > 0
        assert result.risk_amount > 0

    def test_reject_no_signal(self):
        """Should reject when has_signal is False."""
        signal = self._make_signal(has_signal=False)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is False

    def test_reject_open_trade_exists(self):
        """Should reject when an open trade already exists."""
        signal = self._make_signal()
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=True,
        )
        assert result.approved is False
        assert "open trade" in result.rejection_reasons[0].lower()

    def test_reject_stop_loss_above_entry(self):
        """Should reject when stop-loss is above entry."""
        signal = self._make_signal(stop_loss=66000.0)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is False
        assert "stop-loss" in result.rejection_reasons[0].lower()

    def test_reject_low_risk_reward(self):
        """Should reject when risk/reward is below minimum."""
        signal = self._make_signal(risk_reward=1.5)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is False
        assert "risk/reward" in result.rejection_reasons[0].lower()

    def test_reject_take_profit_below_entry(self):
        """Should reject when take-profit is below entry."""
        signal = self._make_signal(take_profit=60000.0)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is False
        assert "take-profit" in result.rejection_reasons[0].lower()

    def test_short_approved_signal(self):
        """Valid SHORT signal should be approved."""
        signal = self._make_signal(side="SHORT", stop_loss=68000.0, take_profit=59000.0)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is True
        assert result.quantity > 0
        assert result.risk_amount > 0

    def test_short_reject_stop_loss_below_entry(self):
        """Should reject when stop-loss is below entry for SHORT."""
        signal = self._make_signal(side="SHORT", stop_loss=60000.0, take_profit=59000.0)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is False
        assert "stop-loss" in result.rejection_reasons[0].lower()

    def test_short_reject_take_profit_above_entry(self):
        """Should reject when take-profit is above entry for SHORT."""
        signal = self._make_signal(side="SHORT", stop_loss=68000.0, take_profit=70000.0)
        result = validate_signal(
            signal=signal,
            account_balance=10000,
            risk_per_trade=0.01,
            min_risk_reward=2.0,
            has_open_trade=False,
        )
        assert result.approved is False
        assert "take-profit" in result.rejection_reasons[0].lower()
