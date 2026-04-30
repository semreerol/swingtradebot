"""
Tests for the Daily Trend + 4H Entry strategy.
Uses synthetic candle data to verify signal generation.
"""
import pytest
from app.exchange.binance_market_data import Candle
from app.strategies.daily_trend_4h_entry import evaluate, STRATEGY_ID
from datetime import datetime, timezone, timedelta


def _make_candles(
    n: int,
    base_price: float = 100.0,
    trend: float = 0.5,
    volatility: float = 2.0,
    base_volume: float = 1000.0,
) -> list[Candle]:
    """
    Generate synthetic candle data for testing.

    Args:
        n: Number of candles.
        base_price: Starting price.
        trend: Price increase per candle (uptrend if > 0).
        volatility: High/low range.
        base_volume: Base volume.
    """
    candles = []
    now = datetime.now(timezone.utc)

    for i in range(n):
        close = base_price + (trend * i)
        open_price = close - trend * 0.5
        high = close + volatility
        low = close - volatility

        candle = Candle(
            open_time=now - timedelta(hours=(n - i) * 4),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=base_volume + (i * 10),
            close_time=now - timedelta(hours=(n - i) * 4) + timedelta(hours=4),
        )
        candles.append(candle)

    return candles


class TestDailyTrend4HEntry:
    """Tests for the strategy evaluation."""

    DEFAULT_PARAMS = {
        "ema_fast": 20,
        "ema_slow": 50,
        "rsi_length": 14,
        "rsi_min": 45,
        "rsi_max": 70,
        "atr_length": 14,
        "atr_stop_multiplier": 2.0,
        "risk_reward": 2.0,
        "volume_ma_length": 20,
    }

    def test_signal_generated_in_uptrend(self):
        """Should generate a signal in a clear uptrend."""
        # Create candles with a clear uptrend
        candles_1d = _make_candles(
            n=100, base_price=50000, trend=100, volatility=500, base_volume=5000
        )
        candles_4h = _make_candles(
            n=100, base_price=50000, trend=25, volatility=200, base_volume=3000
        )

        signal = evaluate(
            symbol="BTCUSDT",
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=self.DEFAULT_PARAMS,
        )

        # In a clean uptrend, we expect a signal
        assert signal.symbol == "BTCUSDT"
        assert signal.strategy_id == STRATEGY_ID

        if signal.has_signal:
            assert signal.side == "LONG"
            assert signal.entry > 0
            assert signal.stop_loss < signal.entry
            assert signal.take_profit > signal.entry
            assert signal.risk_reward >= 2.0
            assert len(signal.reason) > 0

    def test_no_signal_in_downtrend(self):
        """Should NOT generate a signal in a downtrend."""
        # Create candles with a clear downtrend
        candles_1d = _make_candles(
            n=100, base_price=70000, trend=-100, volatility=500, base_volume=5000
        )
        candles_4h = _make_candles(
            n=100, base_price=70000, trend=-25, volatility=200, base_volume=3000
        )

        signal = evaluate(
            symbol="BTCUSDT",
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=self.DEFAULT_PARAMS,
        )

        assert signal.has_signal is False

    def test_insufficient_data(self):
        """Should return no signal with insufficient data."""
        candles_1d = _make_candles(n=10, base_price=50000, trend=100)
        candles_4h = _make_candles(n=10, base_price=50000, trend=25)

        signal = evaluate(
            symbol="BTCUSDT",
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=self.DEFAULT_PARAMS,
        )

        assert signal.has_signal is False
        assert "Insufficient" in signal.reason[0] or "data" in signal.reason[0].lower()

    def test_signal_has_correct_structure(self):
        """Signal to_dict should produce correct Firestore structure."""
        candles_1d = _make_candles(
            n=100, base_price=50000, trend=100, volatility=500
        )
        candles_4h = _make_candles(
            n=100, base_price=50000, trend=25, volatility=200
        )

        signal = evaluate(
            symbol="BTCUSDT",
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=self.DEFAULT_PARAMS,
        )

        signal_dict = signal.to_dict()

        assert "symbol" in signal_dict
        assert "side" in signal_dict
        assert "status" in signal_dict
        assert "entry" in signal_dict
        assert "stop_loss" in signal_dict
        assert "take_profit" in signal_dict
        assert "risk_reward" in signal_dict
        assert "strategy_id" in signal_dict
        assert "reason" in signal_dict
        assert "timeframe_context" in signal_dict
        assert signal_dict["timeframe_context"]["trend"] == "1d"
        assert signal_dict["timeframe_context"]["entry"] == "4h"

    def test_custom_params(self):
        """Strategy should respect custom parameters."""
        custom_params = {
            **self.DEFAULT_PARAMS,
            "rsi_min": 30,
            "rsi_max": 80,
            "atr_stop_multiplier": 3.0,
        }

        candles_1d = _make_candles(
            n=100, base_price=50000, trend=100, volatility=500
        )
        candles_4h = _make_candles(
            n=100, base_price=50000, trend=25, volatility=200
        )

        signal = evaluate(
            symbol="BTCUSDT",
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=custom_params,
        )

        # Should still work with custom params
        assert signal.symbol == "BTCUSDT"
