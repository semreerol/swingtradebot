import argparse
import sys
from datetime import datetime
import json

from app.exchange.binance_market_data import fetch_klines
from app.strategies.daily_trend_4h_score_long_short import DailyTrend4HScoreLongShortStrategy
from app.strategies.daily_trend_4h_entry import evaluate as evaluate_v1
from app.firebase.repositories import DEFAULT_STRATEGY_CONFIG
from app.execution.paper_executor import create_paper_trade, check_open_trade
from app.risk.risk_manager import validate_signal

def parse_args():
    parser = argparse.ArgumentParser(description="Swing Trade Bot Backtest Runner")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--strategy", type=str, default="daily_trend_4h_score_long_short_v3", help="Strategy ID")
    parser.add_argument("--limit", type=int, default=1000, help="Number of 4H candles to fetch (max 1000 for binance)")
    return parser.parse_args()

def run_backtest(symbol: str, strategy_id: str, limit: int):
    print(f"Starting backtest for {symbol} using strategy {strategy_id}...")
    
    # Fetch historical data
    print("Fetching historical data from Binance...")
    candles_4h = fetch_klines(symbol, "4h", limit=limit)
    candles_1d = fetch_klines(symbol, "1d", limit=limit // 6) # Approximation
    
    btc_candles_1d = None
    if symbol != "BTCUSDT":
        btc_candles_1d = fetch_klines("BTCUSDT", "1d", limit=limit // 6)
        
    print(f"Fetched {len(candles_4h)} 4H candles and {len(candles_1d)} 1D candles.")

    params = DEFAULT_STRATEGY_CONFIG["params"]
    
    open_trade = None
    trades_history = []
    
    # We need at least 60 candles to start evaluating
    start_idx = 60
    if start_idx >= len(candles_4h):
        print("Not enough 4H candles for backtesting.")
        return

    print("Running simulation...")
    for i in range(start_idx, len(candles_4h)):
        current_candle = candles_4h[i]
        current_price = current_candle.close
        
        # If there's an open trade, check it
        if open_trade:
            # Simple simulation: we check high/low for stop/target
            # This is an approximation as we don't know intra-candle path. We'll be conservative as requested.
            side = open_trade.get("side", "LONG")
            sl = open_trade["stop_loss"]
            tp = open_trade["take_profit"]
            
            close_reason = None
            exit_price = None
            
            # Update MFE/MAE
            open_trade["max_price_seen"] = max(open_trade.get("max_price_seen", current_price), current_candle.high)
            open_trade["min_price_seen"] = min(open_trade.get("min_price_seen", current_price), current_candle.low)
            
            if side == "LONG":
                # Conservative: check stop first
                if current_candle.low <= sl:
                    close_reason, updates = check_open_trade(open_trade, sl)
                elif current_candle.high >= tp:
                    close_reason, updates = check_open_trade(open_trade, tp)
                else:
                    close_reason, updates = check_open_trade(open_trade, current_price)
            else: # SHORT
                if current_candle.high >= sl:
                    close_reason, updates = check_open_trade(open_trade, sl)
                elif current_candle.low <= tp:
                    close_reason, updates = check_open_trade(open_trade, tp)
                else:
                    close_reason, updates = check_open_trade(open_trade, current_price)
                    
            if close_reason and close_reason != "CLOSED_BY_TIMEOUT":
                # Apply updates
                open_trade.update(updates)
                trades_history.append(open_trade)
                open_trade = None
            elif close_reason == "CLOSED_BY_TIMEOUT":
                open_trade.update(updates)
                trades_history.append(open_trade)
                open_trade = None
            else:
                # Still open, update metrics
                open_trade.update(updates)
                
            continue # Don't open a new trade while one is open
            
        # No open trade, look for signals
        # We slice the array up to the current index
        hist_4h = candles_4h[:i+1]
        
        # Approximate the 1D slice (1d candle roughly covers 6 4h candles)
        # To be completely safe against lookahead, we could use current_candle.close_time
        hist_1d = [c for c in candles_1d if c.open_time <= current_candle.open_time]
        
        hist_btc_1d = None
        if btc_candles_1d:
            hist_btc_1d = [c for c in btc_candles_1d if c.open_time <= current_candle.open_time]

        if strategy_id == "daily_trend_4h_score_long_short_v3":
            strategy = DailyTrend4HScoreLongShortStrategy()
            signal = strategy.evaluate(symbol, hist_1d, hist_4h, params, hist_btc_1d)
        else:
            signal = evaluate_v1(symbol, hist_1d, hist_4h, params)
            
        if signal.has_signal:
            risk_result = validate_signal(signal, 10000, 0.01, 2.0, False)
            if risk_result.approved:
                open_trade = create_paper_trade(signal, risk_result, 14)
                
    # Close any remaining trade at the end
    if open_trade:
        close_reason, updates = check_open_trade(open_trade, candles_4h[-1].close)
        open_trade.update(updates)
        if not open_trade.get("status", "").startswith("CLOSED"):
            open_trade["status"] = "CLOSED_BY_END_OF_BACKTEST"
            open_trade["exit_price"] = candles_4h[-1].close
            side = open_trade["side"]
            entry = open_trade["entry"]
            qty = open_trade["quantity"]
            if side == "LONG":
                pnl = (open_trade["exit_price"] - entry) * qty
            else:
                pnl = (entry - open_trade["exit_price"]) * qty
            open_trade["pnl"] = pnl
        trades_history.append(open_trade)

    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    
    total_trades = len(trades_history)
    if total_trades == 0:
        print("No trades executed.")
        return
        
    long_trades = [t for t in trades_history if t["side"] == "LONG"]
    short_trades = [t for t in trades_history if t["side"] == "SHORT"]
    
    long_wins = [t for t in long_trades if t.get("pnl", 0) > 0]
    short_wins = [t for t in short_trades if t.get("pnl", 0) > 0]
    
    long_net_pnl = sum(t.get("pnl", 0) for t in long_trades)
    short_net_pnl = sum(t.get("pnl", 0) for t in short_trades)
    
    long_gross_profit = sum(t.get("pnl", 0) for t in long_trades if t.get("pnl", 0) > 0)
    long_gross_loss = abs(sum(t.get("pnl", 0) for t in long_trades if t.get("pnl", 0) < 0))
    
    short_gross_profit = sum(t.get("pnl", 0) for t in short_trades if t.get("pnl", 0) > 0)
    short_gross_loss = abs(sum(t.get("pnl", 0) for t in short_trades if t.get("pnl", 0) < 0))
    
    long_pf = (long_gross_profit / long_gross_loss) if long_gross_loss > 0 else float("inf")
    short_pf = (short_gross_profit / short_gross_loss) if short_gross_loss > 0 else float("inf")
    
    print(f"Total Trades: {total_trades}")
    print(f"Net PnL: ${long_net_pnl + short_net_pnl:.2f}")
    print(f"Win Rate: {((len(long_wins) + len(short_wins)) / total_trades) * 100:.1f}%")
    print(f"Side Distribution: {len(long_trades)} Longs / {len(short_trades)} Shorts")
    
    print("\n--- LONG PERFORMANCE ---")
    print(f"Long Trades: {len(long_trades)}")
    print(f"Long Net PnL: ${long_net_pnl:.2f}")
    if len(long_trades) > 0:
        print(f"Long Win Rate: {(len(long_wins) / len(long_trades)) * 100:.1f}%")
        print(f"Long Profit Factor: {long_pf:.2f}")
        
    print("\n--- SHORT PERFORMANCE ---")
    print(f"Short Trades: {len(short_trades)}")
    print(f"Short Net PnL: ${short_net_pnl:.2f}")
    if len(short_trades) > 0:
        print(f"Short Win Rate: {(len(short_wins) / len(short_trades)) * 100:.1f}%")
        print(f"Short Profit Factor: {short_pf:.2f}")

if __name__ == "__main__":
    args = parse_args()
    run_backtest(args.symbol, args.strategy, args.limit)
