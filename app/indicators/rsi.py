"""
Relative Strength Index (RSI) indicator.
"""


def calculate_rsi(values: list[float], period: int = 14) -> list[float]:
    """
    Calculate the Relative Strength Index using Wilder's smoothing method.

    Args:
        values: List of price values (typically close prices).
        period: RSI period (default 14).

    Returns:
        List of RSI values. The first `period` entries are 0.0 (not enough data).
        The returned list has the same length as the input.

    Raises:
        ValueError: If values list is shorter than period + 1.
    """
    if len(values) < period + 1:
        raise ValueError(
            f"Not enough data to calculate RSI({period}). "
            f"Got {len(values)} values, need at least {period + 1}."
        )

    rsi_values: list[float] = [0.0] * period

    # Calculate price changes
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]

    # Initial average gain/loss (SMA of first `period` changes)
    gains = [max(d, 0.0) for d in deltas[:period]]
    losses = [abs(min(d, 0.0)) for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # First RSI value
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    # Subsequent RSI values using Wilder's smoothing
    for i in range(period, len(deltas)):
        delta = deltas[i]
        gain = max(delta, 0.0)
        loss = abs(min(delta, 0.0))

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi_values
