"""
Daily Trend + 4H Entry Score Long/Short Strategy.

Evaluates both LONG and SHORT candidates.
Compares scores and generates a signal for the highest scoring side.
"""
from typing import Any
import math

from app.exchange.binance_market_data import Candle
from app.indicators.ema import calculate_ema
from app.indicators.rsi import calculate_rsi
from app.indicators.atr import calculate_atr
from app.strategies.base import StrategySignal
from app.utils.logger import get_logger

logger = get_logger("strategies.daily_trend_4h_score_long_short")

STRATEGY_ID = "daily_trend_4h_score_long_short_v3"

def calculate_slope_percent(values: list[float], lookback: int = 5) -> float:
    if len(values) < lookback + 1:
        return 0.0
    current = values[-1]
    past = values[-(lookback + 1)]
    if past == 0:
        return 0.0
    return ((current - past) / past) * 100.0

def classify_slope_regime(slope_percent: float) -> str:
    if slope_percent >= 1.0:
        return "strong_positive"
    elif 0.0 <= slope_percent < 1.0:
        return "weak_positive"
    elif -1.0 <= slope_percent < 0.0:
        return "weak_negative"
    else:
        return "strong_negative"

class DailyTrend4HScoreLongShortStrategy:
    """Strategy class that evaluates both LONG and SHORT paper trade setups."""
    
    def evaluate(
        self,
        symbol: str,
        candles_1d: list[Candle],
        candles_4h: list[Candle],
        params: dict[str, Any],
        btc_candles_1d: list[Candle] = None
    ) -> StrategySignal:
        
        # ── Parameter Extraction ─────────────────────────────────────────────
        min_score = params.get("min_score_to_trade", 75)
        allow_long = params.get("allow_long", True)
        allow_short = params.get("allow_short", True)
        btc_filter_enabled = params.get("btc_filter_enabled", True)
        btc_filter_reject_opposite = params.get("btc_filter_reject_opposite", True)
        
        # Default empty signal
        base_signal = StrategySignal(
            has_signal=False,
            symbol=symbol,
            side="NONE",
            strategy_id=STRATEGY_ID
        )
        
        # Validation
        if len(candles_1d) < 60 or len(candles_4h) < 60:
            base_signal.warnings.append("Insufficient data")
            return base_signal
            
        # BTC Market Filter Evaluation
        btc_market_regime = "mixed"
        if btc_filter_enabled:
            # If symbol is BTCUSDT or btc_candles_1d is None, use its own candles
            btc_target = btc_candles_1d if btc_candles_1d and symbol != "BTCUSDT" else candles_1d
            closes_btc_1d = [c.close for c in btc_target]
            ema50_btc = calculate_ema(closes_btc_1d, params.get("ema_slow", 50))
            if len(ema50_btc) >= 6:
                btc_slope = calculate_slope_percent(ema50_btc, params.get("slope_lookback", 5))
                last_btc_close = closes_btc_1d[-1]
                last_btc_ema = ema50_btc[-1]
                
                if last_btc_close > last_btc_ema and btc_slope >= 0:
                    btc_market_regime = "positive"
                elif last_btc_close < last_btc_ema and btc_slope <= 0:
                    btc_market_regime = "negative"

        # Evaluate Candidates
        long_cand = self.evaluate_long(symbol, candles_1d, candles_4h, params, btc_market_regime, btc_filter_reject_opposite) if allow_long else None
        short_cand = self.evaluate_short(symbol, candles_1d, candles_4h, params, btc_market_regime, btc_filter_reject_opposite) if allow_short else None
        
        long_score = long_cand.score if long_cand else 0
        short_score = short_cand.score if short_cand else 0
        
        # Output metric variables
        metrics = {
            "long_score": long_score,
            "short_score": short_score,
            "btc_market_filter": btc_market_regime,
            "long_rejected_reasons": long_cand.reason if long_cand and not long_cand.has_signal else [],
            "short_rejected_reasons": short_cand.reason if short_cand and not short_cand.has_signal else [],
            "long_grade": long_cand.grade if long_cand else "",
            "short_grade": short_cand.grade if short_cand else "",
            "selected_side": "NONE"
        }

        # Selection Logic
        valid_long = long_cand is not None and long_cand.has_signal and long_score >= min_score
        valid_short = short_cand is not None and short_cand.has_signal and short_score >= min_score
        
        if valid_long and valid_short:
            if long_score > short_score:
                selected = long_cand
            elif short_score > long_score:
                selected = short_cand
            else:
                base_signal.warnings.append("Long and short scores tied; skipped for safety")
                base_signal.score = long_score
                base_signal.metrics = metrics
                return base_signal
        elif valid_long:
            selected = long_cand
        elif valid_short:
            selected = short_cand
        else:
            # Neither is valid
            base_signal.score = max(long_score, short_score)
            base_signal.metrics = metrics
            base_signal.reason = metrics["long_rejected_reasons"] + metrics["short_rejected_reasons"]
            return base_signal
            
        # We have a selected signal
        selected.metrics = metrics
        selected.metrics["selected_side"] = selected.side
        selected.metrics["daily_slope_regime"] = long_cand.metrics.get("daily_slope_regime") if selected.side == "LONG" else short_cand.metrics.get("daily_slope_regime")
        return selected

    def get_grade(self, score: float) -> str:
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 75: return "B"
        return "C"

    def evaluate_long(
        self, symbol: str, candles_1d: list[Candle], candles_4h: list[Candle],
        params: dict, btc_regime: str, btc_reject_opp: bool
    ) -> StrategySignal:
        
        sig = StrategySignal(has_signal=True, symbol=symbol, side="LONG", strategy_id=STRATEGY_ID)
        score = 0.0
        reasons = []
        
        closes_1d = [c.close for c in candles_1d]
        ema_fast_1d = calculate_ema(closes_1d, params.get("ema_fast", 20))
        ema_slow_1d = calculate_ema(closes_1d, params.get("ema_slow", 50))
        rsi_1d = calculate_rsi(closes_1d, params.get("rsi_length", 14))
        
        last_close_1d = closes_1d[-1]
        
        # 1D Trend
        if last_close_1d > ema_slow_1d[-1]:
            score += 15
            reasons.append("1D close > EMA50")
        if ema_fast_1d[-1] > ema_slow_1d[-1]:
            score += 10
            reasons.append("1D EMA20 > EMA50")
            
        if params.get("rsi_long_min", 45) <= rsi_1d[-1] <= params.get("rsi_long_max", 70):
            score += 10
            reasons.append(f"1D RSI in range ({rsi_1d[-1]:.1f})")
            
        # 1D Slope
        slope_pct = calculate_slope_percent(ema_slow_1d, params.get("slope_lookback", 5))
        regime = classify_slope_regime(slope_pct)
        sig.metrics["daily_slope_regime"] = regime
        
        if regime == "strong_positive":
            score += 15
        elif regime == "weak_positive":
            score += 8
        elif regime == "weak_negative":
            sig.warnings.append("Weak negative slope")
        elif regime == "strong_negative":
            sig.has_signal = False
            sig.reason.append("Strong negative slope rejected")
            return sig

        # BTC Filter
        if btc_regime == "positive":
            score += 10
        elif btc_regime == "mixed":
            sig.warnings.append("BTC regime mixed")
            score += 3
        elif btc_regime == "negative":
            if btc_reject_opp:
                if symbol == "BTCUSDT":
                    sig.warnings.append("BTC is in negative regime but we score it 0 instead of reject for its own symbol.")
                else:
                    sig.has_signal = False
                    sig.reason.append("BTC market regime is negative (rejected)")
                    return sig

        # 4H Entry
        closes_4h = [c.close for c in candles_4h]
        highs_4h = [c.high for c in candles_4h]
        lows_4h = [c.low for c in candles_4h]
        vols_4h = [c.volume for c in candles_4h]
        
        ema_fast_4h = calculate_ema(closes_4h, params.get("ema_fast", 20))
        ema_slow_4h = calculate_ema(closes_4h, params.get("ema_slow", 50))
        
        if closes_4h[-1] > ema_fast_4h[-1]: score += 10
        if ema_fast_4h[-1] > ema_slow_4h[-1]: score += 10
        
        # Bullish Breakout
        lookback = params.get("breakout_lookback", 20)
        recent_closes = closes_4h[-(lookback+1):-1]
        highest_close = max(recent_closes) if recent_closes else closes_4h[-1]
        tolerance = params.get("near_breakout_tolerance_percent", 0.3)
        if closes_4h[-1] >= highest_close * (1 - tolerance/100.0):
            score += 15
            reasons.append("Bullish breakout or near breakout confirmed")
            
        # Volume
        vol_len = params.get("volume_ma_length", 20)
        recent_vols = vols_4h[-vol_len:]
        avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1
        vol_ratio = vols_4h[-1] / avg_vol if avg_vol > 0 else 0
        
        if vol_ratio >= params.get("volume_ratio_strong", 1.2):
            score += 10
        elif vol_ratio >= params.get("volume_ratio_min", 1.0):
            score += 5
        else:
            sig.warnings.append("Low volume")
            
        # ATR
        atr_len = params.get("atr_length", 14)
        atrs = calculate_atr(highs_4h, lows_4h, closes_4h, atr_len)
        last_atr = atrs[-1]
        atr_pct = (last_atr / closes_4h[-1]) * 100
        
        if params.get("atr_percent_min", 1.0) <= atr_pct <= params.get("atr_percent_max", 8.0):
            score += 10
        else:
            sig.warnings.append(f"ATR % {atr_pct:.2f} out of bounds")

        sig.score = score
        sig.grade = self.get_grade(score)
        
        if sig.has_signal:
            sig.entry = closes_4h[-1]
            sig.stop_loss = sig.entry - (last_atr * params.get("atr_stop_multiplier", 2.0))
            if sig.stop_loss >= sig.entry:
                sig.has_signal = False
                sig.reason.append("Stop loss >= entry")
                return sig
            sig.risk_reward = params.get("risk_reward", 2.0)
            sig.take_profit = sig.entry + ((sig.entry - sig.stop_loss) * sig.risk_reward)
            sig.reason = reasons
            
        return sig

    def evaluate_short(
        self, symbol: str, candles_1d: list[Candle], candles_4h: list[Candle],
        params: dict, btc_regime: str, btc_reject_opp: bool
    ) -> StrategySignal:
        
        sig = StrategySignal(has_signal=True, symbol=symbol, side="SHORT", strategy_id=STRATEGY_ID)
        score = 0.0
        reasons = []
        
        closes_1d = [c.close for c in candles_1d]
        ema_fast_1d = calculate_ema(closes_1d, params.get("ema_fast", 20))
        ema_slow_1d = calculate_ema(closes_1d, params.get("ema_slow", 50))
        rsi_1d = calculate_rsi(closes_1d, params.get("rsi_length", 14))
        
        last_close_1d = closes_1d[-1]
        
        # 1D Trend
        if last_close_1d < ema_slow_1d[-1]:
            score += 15
            reasons.append("1D close < EMA50")
        if ema_fast_1d[-1] < ema_slow_1d[-1]:
            score += 10
            reasons.append("1D EMA20 < EMA50")
            
        if params.get("rsi_short_min", 30) <= rsi_1d[-1] <= params.get("rsi_short_max", 55):
            score += 10
            reasons.append(f"1D RSI in range ({rsi_1d[-1]:.1f})")
            
        # 1D Slope
        slope_pct = calculate_slope_percent(ema_slow_1d, params.get("slope_lookback", 5))
        regime = classify_slope_regime(slope_pct)
        sig.metrics["daily_slope_regime"] = regime
        
        if regime == "strong_negative":
            score += 15
        elif regime == "weak_negative":
            score += 8
        elif regime == "weak_positive":
            sig.warnings.append("Weak positive slope")
        elif regime == "strong_positive":
            sig.has_signal = False
            sig.reason.append("Strong positive slope rejected")
            return sig

        # BTC Filter
        if btc_regime == "negative":
            score += 10
        elif btc_regime == "mixed":
            sig.warnings.append("BTC regime mixed")
            score += 3
        elif btc_regime == "positive":
            if btc_reject_opp:
                if symbol == "BTCUSDT":
                    sig.warnings.append("BTC is in positive regime but we score it 0 instead of reject for its own symbol.")
                else:
                    sig.has_signal = False
                    sig.reason.append("BTC market regime is positive (rejected)")
                    return sig

        # 4H Entry
        closes_4h = [c.close for c in candles_4h]
        highs_4h = [c.high for c in candles_4h]
        lows_4h = [c.low for c in candles_4h]
        vols_4h = [c.volume for c in candles_4h]
        
        ema_fast_4h = calculate_ema(closes_4h, params.get("ema_fast", 20))
        ema_slow_4h = calculate_ema(closes_4h, params.get("ema_slow", 50))
        
        if closes_4h[-1] < ema_fast_4h[-1]: score += 10
        if ema_fast_4h[-1] < ema_slow_4h[-1]: score += 10
        
        # Bearish Breakdown
        lookback = params.get("breakout_lookback", 20)
        recent_closes = closes_4h[-(lookback+1):-1]
        lowest_close = min(recent_closes) if recent_closes else closes_4h[-1]
        tolerance = params.get("near_breakout_tolerance_percent", 0.3)
        if closes_4h[-1] <= lowest_close * (1 + tolerance/100.0):
            score += 15
            reasons.append("Bearish breakdown or near breakdown confirmed")
            
        # Volume
        vol_len = params.get("volume_ma_length", 20)
        recent_vols = vols_4h[-vol_len:]
        avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1
        vol_ratio = vols_4h[-1] / avg_vol if avg_vol > 0 else 0
        
        if vol_ratio >= params.get("volume_ratio_strong", 1.2):
            score += 10
        elif vol_ratio >= params.get("volume_ratio_min", 1.0):
            score += 5
        else:
            sig.warnings.append("Low volume")
            
        # ATR
        atr_len = params.get("atr_length", 14)
        atrs = calculate_atr(highs_4h, lows_4h, closes_4h, atr_len)
        last_atr = atrs[-1]
        atr_pct = (last_atr / closes_4h[-1]) * 100
        
        if params.get("atr_percent_min", 1.0) <= atr_pct <= params.get("atr_percent_max", 8.0):
            score += 10
        else:
            sig.warnings.append(f"ATR % {atr_pct:.2f} out of bounds")

        sig.score = score
        sig.grade = self.get_grade(score)
        
        if sig.has_signal:
            sig.entry = closes_4h[-1]
            sig.stop_loss = sig.entry + (last_atr * params.get("atr_stop_multiplier", 2.0))
            if sig.stop_loss <= sig.entry:
                sig.has_signal = False
                sig.reason.append("Stop loss <= entry")
                return sig
            sig.risk_reward = params.get("risk_reward", 2.0)
            sig.take_profit = sig.entry - ((sig.stop_loss - sig.entry) * sig.risk_reward)
            sig.reason = reasons
            
        return sig
