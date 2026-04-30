"""
Tests for paper executor.
"""
from datetime import datetime, timezone
import pytest

from app.execution.paper_executor import create_paper_trade, check_open_trade

def test_short_pnl():
    trade_data = {
        "side": "SHORT",
        "entry": 100.0,
        "stop_loss": 104.0,
        "take_profit": 92.0,
        "quantity": 1.0,
    }
    
    # Hit Take Profit
    close_reason, updates = check_open_trade(trade_data, 92.0)
    assert close_reason == "CLOSED_BY_TARGET"
    assert updates["pnl"] == pytest.approx(8.0)
    assert updates["pnl_percent"] == pytest.approx(8.0)
    
def test_short_stop_loss():
    trade_data = {
        "side": "SHORT",
        "entry": 100.0,
        "stop_loss": 104.0,
        "take_profit": 92.0,
        "quantity": 1.0,
    }
    
    # Hit Stop Loss
    close_reason, updates = check_open_trade(trade_data, 104.0)
    assert close_reason == "CLOSED_BY_STOP"
    assert updates["pnl"] == pytest.approx(-4.0)
    
def test_short_mfe_mae():
    trade_data = {
        "side": "SHORT",
        "entry": 100.0,
        "stop_loss": 110.0,
        "take_profit": 90.0,
        "quantity": 1.0,
        "max_price_seen": 100.0,
        "min_price_seen": 100.0
    }
    
    # Price goes up to 103 (adverse for short)
    close_reason, updates = check_open_trade(trade_data, 103.0)
    assert close_reason is None
    assert updates["mae_percent"] == pytest.approx(-3.0)
    assert updates["mfe_percent"] == pytest.approx(0.0)
    
    # Now simulate price goes down to 95 (favorable for short)
    trade_data["max_price_seen"] = updates["max_price_seen"]
    trade_data["min_price_seen"] = updates["min_price_seen"]
    
    close_reason, updates = check_open_trade(trade_data, 95.0)
    assert close_reason is None
    assert updates["mae_percent"] == pytest.approx(-3.0)
    assert updates["mfe_percent"] == pytest.approx(5.0)

def test_long_mfe_mae():
    trade_data = {
        "side": "LONG",
        "entry": 100.0,
        "stop_loss": 90.0,
        "take_profit": 110.0,
        "quantity": 1.0,
        "max_price_seen": 100.0,
        "min_price_seen": 100.0
    }
    
    # Price goes down to 95 (adverse for long)
    close_reason, updates = check_open_trade(trade_data, 95.0)
    assert close_reason is None
    assert updates["mae_percent"] == pytest.approx(-5.0)
    assert updates["mfe_percent"] == pytest.approx(0.0)
    
    # Price goes up to 103 (favorable for long)
    trade_data["max_price_seen"] = updates["max_price_seen"]
    trade_data["min_price_seen"] = updates["min_price_seen"]
    
    close_reason, updates = check_open_trade(trade_data, 103.0)
    assert close_reason is None
    assert updates["mae_percent"] == pytest.approx(-5.0)
    assert updates["mfe_percent"] == pytest.approx(3.0)
