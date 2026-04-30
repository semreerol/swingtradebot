"""
Binance public market data client.
Fetches OHLCV candle data and current price using the public REST API.
No API key required.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from app.utils.logger import get_logger

logger = get_logger("exchange.binance")

BASE_URL = "https://api.binance.com/api/v3"
KLINES_ENDPOINT = f"{BASE_URL}/klines"
TICKER_PRICE_ENDPOINT = f"{BASE_URL}/ticker/price"

REQUEST_TIMEOUT = 30


@dataclass
class Candle:
    """Normalized OHLCV candle data."""

    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime


def _timestamp_to_utc(ms: int) -> datetime:
    """Convert Binance millisecond timestamp to UTC datetime."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[Candle]:
    """
    Fetch OHLCV kline/candlestick data from Binance.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT").
        interval: Candle interval (e.g., "1d", "4h").
        limit: Number of candles to fetch (max 1000).

    Returns:
        List of Candle objects sorted by open_time ascending.

    Raises:
        requests.RequestException: On network or API error.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    logger.info(f"Fetching {limit} {interval} candles for {symbol}...")
    response = requests.get(KLINES_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    raw_klines = response.json()
    candles: list[Candle] = []

    for k in raw_klines:
        candle = Candle(
            open_time=_timestamp_to_utc(k[0]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
            volume=float(k[5]),
            close_time=_timestamp_to_utc(k[6]),
        )
        candles.append(candle)

    logger.info(f"Fetched {len(candles)} candles for {symbol} ({interval}).")
    return candles


def fetch_current_price(symbol: str) -> float:
    """
    Fetch the current price for a symbol.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT").

    Returns:
        Current price as float.

    Raises:
        requests.RequestException: On network or API error.
        ValueError: If price data is missing.
    """
    params = {"symbol": symbol}
    logger.info(f"Fetching current price for {symbol}...")

    response = requests.get(
        TICKER_PRICE_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    data = response.json()
    price = float(data["price"])
    logger.info(f"Current price for {symbol}: {price}")
    return price

