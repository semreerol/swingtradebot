"""
Risk Manager.
Validates signals against risk rules before allowing trade creation.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from app.risk.position_sizer import calculate_position_size
from app.strategies.base import StrategySignal
from app.utils.logger import get_logger

logger = get_logger("risk.risk_manager")


@dataclass
class RiskResult:
    """Result of risk validation."""

    approved: bool
    quantity: float = 0.0
    risk_amount: float = 0.0
    rejection_reasons: list[str] = field(default_factory=list)


def validate_signal(
    signal: StrategySignal,
    account_balance: float,
    risk_per_trade: float,
    min_risk_reward: float,
    has_open_trade: bool,
) -> RiskResult:
    """
    Validate a strategy signal against risk management rules.

    Args:
        signal: The strategy signal to validate.
        account_balance: Current account balance.
        risk_per_trade: Maximum risk percentage per trade.
        min_risk_reward: Minimum acceptable risk/reward ratio.
        has_open_trade: Whether there is already an open trade.

    Returns:
        RiskResult with approval status and details.
    """
    reasons: list[str] = []

    # Rule 1: No signal, no trade
    if not signal.has_signal:
        return RiskResult(approved=False, rejection_reasons=["No signal generated"])

    # Rule 2: Already have an open trade
    if has_open_trade:
        reasons.append("An open trade already exists (max 1 allowed)")
        logger.warning("Risk manager: rejected — open trade exists.")
        return RiskResult(approved=False, rejection_reasons=reasons)

    # Rule 3: Stop-loss validation
    if signal.side == "LONG":
        if signal.stop_loss >= signal.entry:
            reasons.append(f"Stop-loss ({signal.stop_loss:.2f}) must be below entry ({signal.entry:.2f}) for LONG")
            logger.warning("Risk manager: rejected — stop-loss >= entry.")
            return RiskResult(approved=False, rejection_reasons=reasons)
        if signal.take_profit <= signal.entry:
            reasons.append(f"Take-profit ({signal.take_profit:.2f}) must be above entry ({signal.entry:.2f}) for LONG")
            logger.warning("Risk manager: rejected — take-profit <= entry.")
            return RiskResult(approved=False, rejection_reasons=reasons)
    elif signal.side == "SHORT":
        if signal.stop_loss <= signal.entry:
            reasons.append(f"Stop-loss ({signal.stop_loss:.2f}) must be above entry ({signal.entry:.2f}) for SHORT")
            logger.warning("Risk manager: rejected — stop-loss <= entry.")
            return RiskResult(approved=False, rejection_reasons=reasons)
        if signal.take_profit >= signal.entry:
            reasons.append(f"Take-profit ({signal.take_profit:.2f}) must be below entry ({signal.entry:.2f}) for SHORT")
            logger.warning("Risk manager: rejected — take-profit >= entry.")
            return RiskResult(approved=False, rejection_reasons=reasons)

    # Rule 5: Minimum risk/reward ratio
    if signal.risk_reward < min_risk_reward:
        reasons.append(
            f"Risk/Reward ({signal.risk_reward:.2f}) below minimum ({min_risk_reward:.2f})"
        )
        logger.warning("Risk manager: rejected — R/R too low.")
        return RiskResult(approved=False, rejection_reasons=reasons)

    # Rule 6: Calculate position size
    try:
        quantity, risk_amount = calculate_position_size(
            account_balance=account_balance,
            risk_per_trade=risk_per_trade,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            side=signal.side,
        )
    except ValueError as e:
        reasons.append(f"Position sizing error: {str(e)}")
        logger.warning(f"Risk manager: rejected — {e}")
        return RiskResult(approved=False, rejection_reasons=reasons)

    # Rule 7: Quantity must be positive
    if quantity <= 0:
        reasons.append(f"Calculated quantity is not positive: {quantity}")
        logger.warning("Risk manager: rejected — quantity <= 0.")
        return RiskResult(approved=False, rejection_reasons=reasons)

    logger.info(
        f"Risk manager: APPROVED | qty={quantity:.8f}, "
        f"risk={risk_amount:.2f}, R/R={signal.risk_reward:.2f}"
    )

    return RiskResult(
        approved=True,
        quantity=quantity,
        risk_amount=risk_amount,
    )
