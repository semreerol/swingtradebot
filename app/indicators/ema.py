"""
Exponential Moving Average (EMA) indicator.
"""


def calculate_ema(values: list[float], period: int) -> list[float]:
    """
    Calculate the Exponential Moving Average.

    Args:
        values: List of price values (typically close prices).
        period: EMA period (e.g., 20, 50).

    Returns:
        List of EMA values. The first (period - 1) values use a
        progressive seed (SMA for the first point, then EMA from there).
        The returned list has the same length as the input.

    Raises:
        ValueError: If values list is shorter than the period.
    """
    if len(values) < period:
        raise ValueError(
            f"Not enough data to calculate EMA({period}). "
            f"Got {len(values)} values, need at least {period}."
        )

    multiplier = 2.0 / (period + 1)
    ema_values: list[float] = []

    # Seed with SMA of the first `period` values
    sma = sum(values[:period]) / period
    ema_values = [0.0] * (period - 1) + [sma]

    # Calculate EMA for the rest
    for i in range(period, len(values)):
        ema = (values[i] - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    return ema_values
