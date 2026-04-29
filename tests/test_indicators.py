"""
Tests for indicator calculations: EMA, RSI, ATR.
"""
import pytest
from app.indicators.ema import calculate_ema
from app.indicators.rsi import calculate_rsi
from app.indicators.atr import calculate_atr


# ═══════════════════════════════════════════════════════════════════════════
# EMA Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEMA:
    """Tests for EMA calculation."""

    def test_ema_basic(self):
        """EMA should produce correct length output."""
        values = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        period = 5
        result = calculate_ema(values, period)
        assert len(result) == len(values)

    def test_ema_first_value_is_sma(self):
        """The first valid EMA value should equal the SMA of the first `period` values."""
        values = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]
        period = 5
        result = calculate_ema(values, period)
        expected_sma = sum(values[:5]) / 5  # (10+12+14+16+18)/5 = 14.0
        assert result[4] == pytest.approx(expected_sma)

    def test_ema_trending_up(self):
        """In an uptrend, EMA should be increasing."""
        values = list(range(1, 21))  # 1 to 20
        period = 5
        result = calculate_ema(values, period)
        # Check last 5 EMA values are increasing
        for i in range(-4, 0):
            assert result[i] > result[i - 1]

    def test_ema_short_data_raises(self):
        """Should raise ValueError if data is shorter than period."""
        with pytest.raises(ValueError, match="Not enough data"):
            calculate_ema([1, 2, 3], 5)

    def test_ema_constant_values(self):
        """EMA of constant values should equal that constant."""
        values = [50.0] * 20
        period = 10
        result = calculate_ema(values, period)
        for v in result[period - 1:]:
            assert v == pytest.approx(50.0)


# ═══════════════════════════════════════════════════════════════════════════
# RSI Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRSI:
    """Tests for RSI calculation."""

    def test_rsi_basic(self):
        """RSI should produce correct length output."""
        values = list(range(1, 30))
        period = 14
        result = calculate_rsi(values, period)
        assert len(result) == len(values)

    def test_rsi_pure_uptrend_is_100(self):
        """Pure uptrend (no down moves) should yield RSI = 100."""
        values = list(range(1, 30))
        period = 14
        result = calculate_rsi(values, period)
        # All RSI values after the initial period should be 100
        for v in result[period:]:
            assert v == pytest.approx(100.0)

    def test_rsi_range(self):
        """RSI values should always be between 0 and 100."""
        values = [100, 102, 98, 103, 97, 105, 99, 106, 95, 110,
                  92, 108, 96, 112, 90, 115, 88, 118, 85, 120]
        period = 14
        result = calculate_rsi(values, period)
        for v in result[period:]:
            assert 0 <= v <= 100

    def test_rsi_short_data_raises(self):
        """Should raise ValueError if data is too short."""
        with pytest.raises(ValueError, match="Not enough data"):
            calculate_rsi([1, 2, 3], 14)


# ═══════════════════════════════════════════════════════════════════════════
# ATR Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestATR:
    """Tests for ATR calculation."""

    def test_atr_basic(self):
        """ATR should produce correct length output."""
        n = 30
        highs = [100 + i * 2 for i in range(n)]
        lows = [100 + i * 2 - 5 for i in range(n)]
        closes = [100 + i * 2 - 2 for i in range(n)]
        period = 14
        result = calculate_atr(highs, lows, closes, period)
        assert len(result) == n

    def test_atr_positive_values(self):
        """ATR values should be non-negative."""
        n = 30
        highs = [100 + i * 2 for i in range(n)]
        lows = [100 + i * 2 - 5 for i in range(n)]
        closes = [100 + i * 2 - 2 for i in range(n)]
        period = 14
        result = calculate_atr(highs, lows, closes, period)
        for v in result[period:]:
            assert v >= 0

    def test_atr_mismatched_lengths_raises(self):
        """Should raise ValueError if input lists have different lengths."""
        with pytest.raises(ValueError, match="same length"):
            calculate_atr([1, 2], [1], [1, 2], 1)

    def test_atr_short_data_raises(self):
        """Should raise ValueError if data is too short."""
        with pytest.raises(ValueError, match="Not enough data"):
            calculate_atr([1, 2], [1, 2], [1, 2], 14)

    def test_atr_constant_range(self):
        """ATR of candles with constant range should converge to that range."""
        n = 50
        # Each candle: high=105, low=95, close=100 → true range = 10
        highs = [105.0] * n
        lows = [95.0] * n
        closes = [100.0] * n
        period = 14
        result = calculate_atr(highs, lows, closes, period)
        # After enough periods, ATR should converge to ~10
        assert result[-1] == pytest.approx(10.0, abs=0.5)
