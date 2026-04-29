"""
Average True Range (ATR) indicator.
"""


def calculate_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float]:
    """
    Calculate the Average True Range.

    Args:
        highs: List of high prices.
        lows: List of low prices.
        closes: List of close prices.
        period: ATR period (default 14).

    Returns:
        List of ATR values. The first `period` entries are 0.0.
        The returned list has the same length as the input.

    Raises:
        ValueError: If input lists are not the same length or too short.
    """
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, and closes must have the same length.")

    if len(highs) < period + 1:
        raise ValueError(
            f"Not enough data to calculate ATR({period}). "
            f"Got {len(highs)} values, need at least {period + 1}."
        )

    # Calculate True Range
    true_ranges: list[float] = [0.0]  # First candle has no previous close
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    # Calculate ATR using Wilder's smoothing
    atr_values: list[float] = [0.0] * period

    # Initial ATR is the SMA of the first `period` true ranges (starting from index 1)
    initial_atr = sum(true_ranges[1 : period + 1]) / period
    atr_values.append(initial_atr)

    # Subsequent ATR values
    for i in range(period + 1, len(true_ranges)):
        atr = (atr_values[-1] * (period - 1) + true_ranges[i]) / period
        atr_values.append(atr)

    return atr_values
