"""
Paper Trade Executor.
Simulates trade execution without sending real orders.
Manages open trade lifecycle: open, check, close.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from app.strategies.base import StrategySignal
from app.risk.risk_manager import RiskResult
from app.utils.logger import get_logger

logger = get_logger("execution.paper_executor")


def create_paper_trade(
    signal: StrategySignal,
    risk_result: RiskResult,
    max_holding_days: int = 14,
) -> dict[str, Any]:
    """
    Create a paper trade from a validated signal.

    Args:
        signal: The approved strategy signal.
        risk_result: The approved risk result with quantity.
        max_holding_days: Maximum days to hold the trade.

    Returns:
        Trade document data ready for Firestore.
    """
    now = datetime.now(timezone.utc)
    max_holding_until = now + timedelta(days=max_holding_days)

    trade_data: dict[str, Any] = {
        "symbol": signal.symbol,
        "side": signal.side,
        "status": "OPEN",
        "mode": "paper",
        "entry": signal.entry,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "quantity": round(risk_result.quantity, 8),
        "risk_amount": round(risk_result.risk_amount, 2),
        "risk_reward": signal.risk_reward,
        "opened_at": now.isoformat(),
        "closed_at": None,
        "max_holding_until": max_holding_until.isoformat(),
        "exit_price": None,
        "pnl": None,
        "pnl_percent": None,
        "max_price_seen": signal.entry,
        "min_price_seen": signal.entry,
        "mfe_percent": 0.0,
        "mae_percent": 0.0,
        "strategy_id": signal.strategy_id,
        "signal_id": None,  # Will be set after signal is saved
    }

    logger.info(
        f"Paper trade created: {signal.symbol} {signal.side} | "
        f"Entry: {signal.entry:.2f} | Qty: {risk_result.quantity:.8f} | "
        f"SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f}"
    )

    return trade_data


def check_open_trade(
    trade_data: dict[str, Any],
    current_price: float,
) -> tuple[Optional[str], dict[str, Any]]:
    """
    Check an open paper trade against current price and holding time.

    Args:
        trade_data: The trade document from Firestore.
        current_price: Current market price.

    Returns:
        Tuple of (close_reason, update_dict).
        close_reason is None if trade remains open.
        close_reason is one of: CLOSED_BY_STOP, CLOSED_BY_TARGET, CLOSED_BY_TIMEOUT.
    """
    entry = trade_data["entry"]
    stop_loss = trade_data["stop_loss"]
    take_profit = trade_data["take_profit"]
    quantity = trade_data["quantity"]
    side = trade_data.get("side", "LONG")
    max_holding_until_str = trade_data.get("max_holding_until", "")
    
    max_price_seen = max(trade_data.get("max_price_seen", entry), current_price)
    min_price_seen = min(trade_data.get("min_price_seen", entry), current_price)
    
    if side == "LONG":
        mfe_percent = ((max_price_seen - entry) / entry) * 100
        mae_percent = ((min_price_seen - entry) / entry) * 100
    else:
        mfe_percent = ((entry - min_price_seen) / entry) * 100
        mae_percent = ((entry - max_price_seen) / entry) * 100

    now = datetime.now(timezone.utc)
    close_reason = None
    exit_price = None

    # Check Stop-Loss
    if (side == "LONG" and current_price <= stop_loss) or (side == "SHORT" and current_price >= stop_loss):
        close_reason = "CLOSED_BY_STOP"
        exit_price = stop_loss
    # Check Take-Profit
    elif (side == "LONG" and current_price >= take_profit) or (side == "SHORT" and current_price <= take_profit):
        close_reason = "CLOSED_BY_TARGET"
        exit_price = take_profit
    # Check Timeout
    elif max_holding_until_str:
        try:
            max_holding_until = datetime.fromisoformat(max_holding_until_str)
            if max_holding_until.tzinfo is None:
                max_holding_until = max_holding_until.replace(tzinfo=timezone.utc)

            if now >= max_holding_until:
                close_reason = "CLOSED_BY_TIMEOUT"
                exit_price = current_price
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse max_holding_until: {e}")
            
    updates = {
        "max_price_seen": max_price_seen,
        "min_price_seen": min_price_seen,
        "mfe_percent": round(mfe_percent, 2),
        "mae_percent": round(mae_percent, 2),
    }

    if close_reason:
        if side == "LONG":
            pnl = (exit_price - entry) * quantity
            pnl_percent = (exit_price - entry) / entry * 100
        else:
            pnl = (entry - exit_price) * quantity
            pnl_percent = (entry - exit_price) / entry * 100

        updates.update({
            "status": close_reason,
            "closed_at": now.isoformat(),
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_percent": round(pnl_percent, 2),
        })

        logger.info(
            f"{close_reason}: price={current_price:.2f} | "
            f"Exit at {exit_price:.2f} | PnL: {pnl:.2f} ({pnl_percent:.2f}%)"
        )
        return close_reason, updates

    # Trade still open
    if side == "LONG":
        unrealized_pnl = (current_price - entry) * quantity
        unrealized_pnl_pct = (current_price - entry) / entry * 100
    else:
        unrealized_pnl = (entry - current_price) * quantity
        unrealized_pnl_pct = (entry - current_price) / entry * 100
        
    logger.info(
        f"Trade still OPEN: price={current_price:.2f} | "
        f"Unrealized PnL: {unrealized_pnl:.2f} ({unrealized_pnl_pct:.2f}%)"
    )

    return None, updates
