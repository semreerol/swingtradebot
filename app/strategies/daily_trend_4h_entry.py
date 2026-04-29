"""
Daily Trend + 4H Entry Strategy.

Uses 1D candles for trend confirmation and 4H candles for entry timing.
Only generates LONG signals.
"""
from typing import Any

from app.exchange.bybit_market_data import Candle
from app.indicators.ema import calculate_ema
from app.indicators.rsi import calculate_rsi
from app.indicators.atr import calculate_atr
from app.strategies.base import StrategySignal
from app.utils.logger import get_logger

logger = get_logger("strategies.daily_trend_4h_entry")

STRATEGY_ID = "daily_trend_4h_entry_v1"


def evaluate(
    symbol: str,
    candles_1d: list[Candle],
    candles_4h: list[Candle],
    params: dict[str, Any],
) -> StrategySignal:
    """
    Evaluate the Daily Trend + 4H Entry strategy.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT").
        candles_1d: Daily candle data (at least 60 candles recommended).
        candles_4h: 4-hour candle data (at least 60 candles recommended).
        params: Strategy parameters from Firestore.

    Returns:
        StrategySignal with has_signal=True if conditions are met.
    """
    no_signal = StrategySignal(has_signal=False, symbol=symbol, strategy_id=STRATEGY_ID)
    reasons: list[str] = []

    # ── Extract Parameters ───────────────────────────────────────────────
    ema_fast_period: int = params.get("ema_fast", 20)
    ema_slow_period: int = params.get("ema_slow", 50)
    rsi_length: int = params.get("rsi_length", 14)
    rsi_min: float = params.get("rsi_min", 45)
    rsi_max: float = params.get("rsi_max", 70)
    atr_length: int = params.get("atr_length", 14)
    atr_stop_multiplier: float = params.get("atr_stop_multiplier", 2.0)
    risk_reward: float = params.get("risk_reward", 2.0)
    volume_ma_length: int = params.get("volume_ma_length", 20)

    # ── Validate Data ────────────────────────────────────────────────────
    min_candles_1d = max(ema_slow_period, rsi_length) + 10
    min_candles_4h = max(ema_slow_period, atr_length, volume_ma_length) + 10

    if len(candles_1d) < min_candles_1d:
        logger.warning(f"Not enough 1D candles: {len(candles_1d)} < {min_candles_1d}")
        no_signal.reason = [f"Insufficient 1D data ({len(candles_1d)} candles)"]
        return no_signal

    if len(candles_4h) < min_candles_4h:
        logger.warning(f"Not enough 4H candles: {len(candles_4h)} < {min_candles_4h}")
        no_signal.reason = [f"Insufficient 4H data ({len(candles_4h)} candles)"]
        return no_signal

    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: Daily Trend Filter (1D)
    # ═══════════════════════════════════════════════════════════════════

    closes_1d = [c.close for c in candles_1d]

    ema_fast_1d = calculate_ema(closes_1d, ema_fast_period)
    ema_slow_1d = calculate_ema(closes_1d, ema_slow_period)
    rsi_1d = calculate_rsi(closes_1d, rsi_length)

    last_close_1d = closes_1d[-1]
    last_ema_fast_1d = ema_fast_1d[-1]
    last_ema_slow_1d = ema_slow_1d[-1]
    last_rsi_1d = rsi_1d[-1]

    # Check: Close > EMA50
    if last_close_1d <= last_ema_slow_1d:
        logger.info(
            f"1D trend filter FAILED: close ({last_close_1d:.2f}) "
            f"<= EMA{ema_slow_period} ({last_ema_slow_1d:.2f})"
        )
        no_signal.reason = [f"1D close below EMA{ema_slow_period}"]
        return no_signal
    reasons.append(f"1D close ({last_close_1d:.2f}) > EMA{ema_slow_period} ({last_ema_slow_1d:.2f})")

    # Check: EMA20 > EMA50
    if last_ema_fast_1d <= last_ema_slow_1d:
        logger.info(
            f"1D trend filter FAILED: EMA{ema_fast_period} ({last_ema_fast_1d:.2f}) "
            f"<= EMA{ema_slow_period} ({last_ema_slow_1d:.2f})"
        )
        no_signal.reason = [f"1D EMA{ema_fast_period} below EMA{ema_slow_period}"]
        return no_signal
    reasons.append(f"1D EMA{ema_fast_period} ({last_ema_fast_1d:.2f}) > EMA{ema_slow_period} ({last_ema_slow_1d:.2f})")

    # Check: RSI between rsi_min and rsi_max
    if not (rsi_min <= last_rsi_1d <= rsi_max):
        logger.info(
            f"1D trend filter FAILED: RSI ({last_rsi_1d:.2f}) "
            f"not in [{rsi_min}, {rsi_max}]"
        )
        no_signal.reason = [f"1D RSI ({last_rsi_1d:.2f}) outside [{rsi_min}-{rsi_max}]"]
        return no_signal
    reasons.append(f"1D RSI ({last_rsi_1d:.2f}) in [{rsi_min}-{rsi_max}]")

    logger.info("1D trend filter PASSED.")

    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: 4H Entry Filter
    # ═══════════════════════════════════════════════════════════════════

    closes_4h = [c.close for c in candles_4h]
    highs_4h = [c.high for c in candles_4h]
    lows_4h = [c.low for c in candles_4h]
    volumes_4h = [c.volume for c in candles_4h]

    ema_fast_4h = calculate_ema(closes_4h, ema_fast_period)
    ema_slow_4h = calculate_ema(closes_4h, ema_slow_period)

    last_close_4h = closes_4h[-1]
    last_ema_fast_4h = ema_fast_4h[-1]
    last_ema_slow_4h = ema_slow_4h[-1]

    # Check: Close > EMA20
    if last_close_4h <= last_ema_fast_4h:
        logger.info(
            f"4H entry filter FAILED: close ({last_close_4h:.2f}) "
            f"<= EMA{ema_fast_period} ({last_ema_fast_4h:.2f})"
        )
        no_signal.reason = [f"4H close below EMA{ema_fast_period}"]
        return no_signal
    reasons.append(f"4H close ({last_close_4h:.2f}) > EMA{ema_fast_period} ({last_ema_fast_4h:.2f})")

    # Check: EMA20 > EMA50
    if last_ema_fast_4h <= last_ema_slow_4h:
        logger.info(
            f"4H entry filter FAILED: EMA{ema_fast_period} ({last_ema_fast_4h:.2f}) "
            f"<= EMA{ema_slow_period} ({last_ema_slow_4h:.2f})"
        )
        no_signal.reason = [f"4H EMA{ema_fast_period} below EMA{ema_slow_period}"]
        return no_signal
    reasons.append(f"4H EMA{ema_fast_period} ({last_ema_fast_4h:.2f}) > EMA{ema_slow_period} ({last_ema_slow_4h:.2f})")

    # Check: Close near or above highest close in last 20 candles
    lookback = min(volume_ma_length, len(closes_4h) - 1)
    recent_closes = closes_4h[-(lookback + 1):-1]  # Exclude current candle
    if recent_closes:
        highest_recent_close = max(recent_closes)
        threshold = highest_recent_close * 0.98  # Within 2% of recent high
        if last_close_4h < threshold:
            logger.info(
                f"4H entry filter FAILED: close ({last_close_4h:.2f}) "
                f"not near highest recent close ({highest_recent_close:.2f})"
            )
            no_signal.reason = [f"4H close not near 20-candle high"]
            return no_signal
        reasons.append(f"4H close near/above recent high ({highest_recent_close:.2f})")

    # Check: Volume above 20-period average (soft pass if no volume)
    if volumes_4h and len(volumes_4h) >= volume_ma_length:
        recent_volumes = volumes_4h[-volume_ma_length:]
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        current_volume = volumes_4h[-1]

        if current_volume > avg_volume:
            reasons.append(
                f"4H volume ({current_volume:.2f}) > avg ({avg_volume:.2f})"
            )
        else:
            # Soft pass: volume below average, but we still proceed with a note
            reasons.append(
                f"4H volume ({current_volume:.2f}) below avg ({avg_volume:.2f}) [soft pass]"
            )
            logger.info("4H volume below average, but proceeding (soft pass).")
    else:
        reasons.append("4H volume data unavailable [soft pass]")
        logger.info("No volume data for filter, proceeding (soft pass).")

    logger.info("4H entry filter PASSED.")

    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: Calculate Entry, Stop-Loss, Take-Profit
    # ═══════════════════════════════════════════════════════════════════

    entry = last_close_4h

    # ATR for stop-loss calculation
    atr_values = calculate_atr(highs_4h, lows_4h, closes_4h, atr_length)
    last_atr = atr_values[-1]

    if last_atr <= 0:
        logger.warning("ATR is zero or negative. Cannot calculate stop-loss.")
        no_signal.reason = ["ATR is zero or negative"]
        return no_signal

    stop_loss = entry - (last_atr * atr_stop_multiplier)

    if stop_loss >= entry:
        logger.warning(f"Stop-loss ({stop_loss:.2f}) >= entry ({entry:.2f}).")
        no_signal.reason = ["Calculated stop-loss >= entry"]
        return no_signal

    risk = entry - stop_loss
    reward = risk * risk_reward
    take_profit = entry + reward
    actual_rr = reward / risk if risk > 0 else 0

    reasons.append(f"Entry: {entry:.2f}")
    reasons.append(f"Stop-loss: {stop_loss:.2f} (ATR: {last_atr:.2f} × {atr_stop_multiplier})")
    reasons.append(f"Take-profit: {take_profit:.2f}")
    reasons.append(f"Risk/Reward: {actual_rr:.2f}")

    logger.info(
        f"SIGNAL GENERATED: {symbol} LONG | "
        f"Entry: {entry:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f} | "
        f"R/R: {actual_rr:.2f}"
    )

    return StrategySignal(
        has_signal=True,
        symbol=symbol,
        side="LONG",
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=round(actual_rr, 2),
        strategy_id=STRATEGY_ID,
        reason=reasons,
    )
