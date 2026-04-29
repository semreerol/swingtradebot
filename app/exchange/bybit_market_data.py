"""
Bybit public market data client.
Fetches OHLCV candle data and current price using the public REST API v5.
No API key required.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from app.utils.logger import get_logger

logger = get_logger("exchange.bybit")

BASE_URL = "https://api.bybit.com/v5/market"
KLINES_ENDPOINT = f"{BASE_URL}/kline"
TICKER_PRICE_ENDPOINT = f"{BASE_URL}/tickers"

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


def _timestamp_to_utc(ms_str: str) -> datetime:
    """Convert Bybit string millisecond timestamp to UTC datetime."""
    return datetime.fromtimestamp(int(ms_str) / 1000, tz=timezone.utc)


def _map_interval(interval: str) -> str:
    """Map standard intervals (1d, 4h) to Bybit v5 intervals (D, 240)."""
    mapping = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
        "1w": "W",
        "1M": "M"
    }
    return mapping.get(interval, "D")


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 200,
) -> list[Candle]:
    """
    Fetch OHLCV kline/candlestick data from Bybit.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT").
        interval: Candle interval (e.g., "1d", "4h").
        limit: Number of candles to fetch (max 1000).

    Returns:
        List of Candle objects sorted by open_time ascending.
    """
    bybit_interval = _map_interval(interval)
    
    params = {
        "category": "spot",
        "symbol": symbol,
        "interval": bybit_interval,
        "limit": limit,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    logger.info(f"Fetching {limit} {interval} candles for {symbol} from Bybit...")
    response = requests.get(KLINES_ENDPOINT, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    if data.get("retCode") != 0:
        raise ValueError(f"Bybit API Error: {data.get('retMsg')}")

    raw_klines = data.get("result", {}).get("list", [])
    candles: list[Candle] = []

    # Bybit returns newest first, we need oldest first
    for k in reversed(raw_klines):
        # Bybit v5 kline format: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]
        candle = Candle(
            open_time=_timestamp_to_utc(k[0]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
            volume=float(k[5]),
            # Bybit v5 does not provide close time explicitly in the list, so we approximate or use open_time
            close_time=_timestamp_to_utc(k[0]) 
        )
        candles.append(candle)

    logger.info(f"Fetched {len(candles)} candles for {symbol} ({interval}).")
    return candles


def fetch_current_price(symbol: str) -> float:
    """
    Fetch the current price for a symbol from Bybit.
    """
    params = {
        "category": "spot",
        "symbol": symbol
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    logger.info(f"Fetching current price for {symbol} from Bybit...")

    response = requests.get(
        TICKER_PRICE_ENDPOINT, params=params, headers=headers, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    data = response.json()
    if data.get("retCode") != 0:
        raise ValueError(f"Bybit API Error: {data.get('retMsg')}")
        
    tickers = data.get("result", {}).get("list", [])
    if not tickers:
        raise ValueError(f"No price data found for {symbol}")

    price = float(tickers[0]["lastPrice"])
    logger.info(f"Current price for {symbol}: {price}")
    return price
