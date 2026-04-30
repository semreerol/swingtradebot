"""
Position sizing calculator.
Determines trade quantity based on risk parameters.
"""
from app.utils.logger import get_logger

logger = get_logger("risk.position_sizer")


def calculate_position_size(
    account_balance: float,
    risk_per_trade: float,
    entry: float,
    stop_loss: float,
    side: str = "LONG",
) -> tuple[float, float]:
    """
    Calculate position size and risk amount.

    Args:
        account_balance: Total account balance in quote currency.
        risk_per_trade: Risk percentage per trade (e.g., 0.01 for 1%).
        entry: Entry price.
        stop_loss: Stop-loss price.
        side: Trade direction ("LONG" or "SHORT").

    Returns:
        Tuple of (quantity, risk_amount).

    Raises:
        ValueError: If inputs are invalid.
    """
    if account_balance <= 0:
        raise ValueError(f"Account balance must be positive: {account_balance}")

    if risk_per_trade <= 0 or risk_per_trade > 1:
        raise ValueError(f"Risk per trade must be between 0 and 1: {risk_per_trade}")

    if side == "LONG" and stop_loss >= entry:
        raise ValueError(f"Stop-loss ({stop_loss}) must be less than entry ({entry}) for LONG.")
    if side == "SHORT" and stop_loss <= entry:
        raise ValueError(f"Stop-loss ({stop_loss}) must be greater than entry ({entry}) for SHORT.")

    risk_amount = account_balance * risk_per_trade
    price_risk = abs(entry - stop_loss)

    if price_risk == 0:
        raise ValueError("Price risk (entry - stop_loss) cannot be zero.")

    quantity = risk_amount / price_risk

    logger.info(
        f"Position sizing: balance={account_balance}, "
        f"risk%={risk_per_trade*100:.1f}%, risk_amount={risk_amount:.2f}, "
        f"price_risk={price_risk:.2f}, quantity={quantity:.8f}"
    )

    return quantity, risk_amount
