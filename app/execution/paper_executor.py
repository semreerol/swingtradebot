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
    max_holding_until_str = trade_data.get("max_holding_until", "")

    now = datetime.now(timezone.utc)

    # Check Stop-Loss
    if current_price <= stop_loss:
        exit_price = stop_loss
        pnl = (exit_price - entry) * quantity
        pnl_percent = (exit_price - entry) / entry * 100

        updates = {
            "status": "CLOSED_BY_STOP",
            "closed_at": now.isoformat(),
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_percent": round(pnl_percent, 2),
        }

        logger.info(
            f"STOP-LOSS HIT: price={current_price:.2f} <= SL={stop_loss:.2f} | "
            f"PnL: {pnl:.2f} ({pnl_percent:.2f}%)"
        )
        return "CLOSED_BY_STOP", updates

    # Check Take-Profit
    if current_price >= take_profit:
        exit_price = take_profit
        pnl = (exit_price - entry) * quantity
        pnl_percent = (exit_price - entry) / entry * 100

        updates = {
            "status": "CLOSED_BY_TARGET",
            "closed_at": now.isoformat(),
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_percent": round(pnl_percent, 2),
        }

        logger.info(
            f"TAKE-PROFIT HIT: price={current_price:.2f} >= TP={take_profit:.2f} | "
            f"PnL: {pnl:.2f} ({pnl_percent:.2f}%)"
        )
        return "CLOSED_BY_TARGET", updates

    # Check Timeout
    if max_holding_until_str:
        try:
            max_holding_until = datetime.fromisoformat(max_holding_until_str)
            if max_holding_until.tzinfo is None:
                max_holding_until = max_holding_until.replace(tzinfo=timezone.utc)

            if now >= max_holding_until:
                exit_price = current_price
                pnl = (exit_price - entry) * quantity
                pnl_percent = (exit_price - entry) / entry * 100

                updates = {
                    "status": "CLOSED_BY_TIMEOUT",
                    "closed_at": now.isoformat(),
                    "exit_price": exit_price,
                    "pnl": round(pnl, 2),
                    "pnl_percent": round(pnl_percent, 2),
                }

                logger.info(
                    f"TIMEOUT: max_holding exceeded | "
                    f"Exit at {exit_price:.2f} | PnL: {pnl:.2f} ({pnl_percent:.2f}%)"
                )
                return "CLOSED_BY_TIMEOUT", updates
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse max_holding_until: {e}")

    # Trade still open — log status check
    unrealized_pnl = (current_price - entry) * quantity
    unrealized_pnl_pct = (current_price - entry) / entry * 100
    logger.info(
        f"Trade still OPEN: price={current_price:.2f} | "
        f"Unrealized PnL: {unrealized_pnl:.2f} ({unrealized_pnl_pct:.2f}%)"
    )

    return None, {}
