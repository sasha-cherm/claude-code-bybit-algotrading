"""
OHLCV data fetcher for Bybit using ccxt.
Fetches historical candles and caches them as parquet files in data/.
"""

import os
import time
from pathlib import Path

import ccxt
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def get_exchange(testnet: bool = False) -> ccxt.bybit:
    """Create a Bybit exchange instance."""
    config = {"enableRateLimit": True}
    if testnet:
        config["sandbox"] = True
    exchange = ccxt.bybit(config)
    exchange.load_markets()
    return exchange


def fetch_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since: str | None = None,
    limit_days: int = 730,
    exchange: ccxt.bybit | None = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV data from Bybit via ccxt.

    Args:
        symbol: Trading pair, e.g. "BTC/USDT"
        timeframe: Candle interval, e.g. "1h", "4h", "1d"
        since: Start date as "YYYY-MM-DD". If None, fetches limit_days back from now.
        limit_days: Number of days to fetch if `since` is not given.
        exchange: Optional pre-created exchange instance.

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
        Index is DatetimeIndex on timestamp.
    """
    if exchange is None:
        exchange = get_exchange()

    if since is not None:
        since_ms = exchange.parse8601(f"{since}T00:00:00Z")
    else:
        since_ms = exchange.milliseconds() - limit_days * 24 * 60 * 60 * 1000

    tf_ms = _timeframe_to_ms(timeframe)
    all_candles = []
    current_since = since_ms
    now_ms = exchange.milliseconds()

    while current_since < now_ms:
        candles = exchange.fetch_ohlcv(
            symbol, timeframe, since=current_since, limit=1000
        )
        if not candles:
            break
        all_candles.extend(candles)
        last_ts = candles[-1][0]
        if last_ts <= current_since:
            break  # no progress, avoid infinite loop
        current_since = last_ts + tf_ms
        if len(candles) < 200:
            break  # clearly reached the end
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(
        all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    df = df.set_index("timestamp")
    return df


def fetch_and_cache(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since: str | None = None,
    limit_days: int = 730,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch OHLCV data with local parquet caching.
    Returns cached data if available and not force_refresh.
    """
    safe_symbol = symbol.replace("/", "_")
    cache_file = DATA_DIR / f"{safe_symbol}_{timeframe}.parquet"

    if cache_file.exists() and not force_refresh:
        df = pd.read_parquet(cache_file)
        # Check if we need to append newer data
        last_cached = df.index.max()
        now = pd.Timestamp.now(tz="UTC")
        tf_ms = _timeframe_to_ms(timeframe)
        gap_ms = (now - last_cached).total_seconds() * 1000
        if gap_ms > tf_ms * 2:
            # Fetch only the missing portion
            exchange = get_exchange()
            since_ms = int(last_cached.timestamp() * 1000) + tf_ms
            new_df = fetch_ohlcv(
                symbol, timeframe,
                since=last_cached.strftime("%Y-%m-%d"),
                exchange=exchange,
            )
            if not new_df.empty:
                df = pd.concat([df, new_df])
                df = df[~df.index.duplicated(keep="last")].sort_index()
                df.to_parquet(cache_file)
        return df

    df = fetch_ohlcv(symbol, timeframe, since=since, limit_days=limit_days)
    if not df.empty:
        df.to_parquet(cache_file)
    return df


def fetch_multiple(
    symbols: list[str],
    timeframe: str = "1h",
    since: str | None = None,
    limit_days: int = 730,
) -> dict[str, pd.DataFrame]:
    """Fetch and cache OHLCV for multiple symbols."""
    result = {}
    for sym in symbols:
        print(f"Fetching {sym} {timeframe}...")
        result[sym] = fetch_and_cache(sym, timeframe, since=since, limit_days=limit_days)
    return result


def _timeframe_to_ms(tf: str) -> int:
    """Convert timeframe string to milliseconds."""
    multipliers = {
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
        "w": 604_800_000,
    }
    unit = tf[-1]
    value = int(tf[:-1])
    return value * multipliers.get(unit, 3_600_000)


if __name__ == "__main__":
    # Quick test: fetch BTC/USDT 1h data for last 30 days
    df = fetch_and_cache("BTC/USDT", "1h", limit_days=30)
    print(f"Fetched {len(df)} candles")
    print(df.tail())
