"""
Bybit Demo Trading Client

Thin wrapper around pybit unified_trading HTTP for demo account operations.
Handles linear perpetuals only (USDT-margined).
"""

import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from pybit.unified_trading import HTTP as _HTTP
except ImportError:
    raise ImportError("Run: pip install pybit")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


DEFAULT_LEVERAGE = 2  # conservative leverage for all positions


class DemoTrader:
    """Bybit demo account interface for linear perpetual futures."""

    def __init__(self):
        api_key = os.getenv("BYBIT_DEMO_API_KEY")
        api_secret = os.getenv("BYBIT_DEMO_API_SECRET")
        if not api_key or not api_secret:
            raise RuntimeError(
                "Set BYBIT_DEMO_API_KEY and BYBIT_DEMO_API_SECRET in .env"
            )
        self.client = _HTTP(api_key=api_key, api_secret=api_secret, demo=True)
        self._leverage_done: set[str] = set()
        self._price_cache: dict[str, float] = {}

    # ── Account ──────────────────────────────────────────────────────────

    def get_equity(self) -> float:
        """Total equity of the Unified account (USDT)."""
        r = self.client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        return float(r["result"]["list"][0]["totalEquity"])

    def get_available_balance(self) -> float:
        """Available balance for trading (not locked in positions)."""
        r = self.client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        return float(r["result"]["list"][0].get("totalAvailableBalance", 0) or 0)

    # ── Positions ─────────────────────────────────────────────────────────

    def get_positions(self) -> dict[str, dict]:
        """
        Fetch all open linear perpetual positions.

        Returns: {bybit_symbol: {side, size, entry_price, notional, pnl}}
          - side: 'Buy' (long) or 'Sell' (short)
          - size: always positive (base currency qty)
          Use get_signed_size() for signed value.
        """
        positions: dict[str, dict] = {}
        cursor = None
        while True:
            kwargs: dict = {
                "category": "linear",
                "settleCoin": "USDT",
                "limit": 200,
            }
            if cursor:
                kwargs["cursor"] = cursor
            r = self.client.get_positions(**kwargs)
            for p in r["result"]["list"]:
                size = float(p.get("size", 0))
                if size > 0:
                    positions[p["symbol"]] = {
                        "side": p["side"],
                        "size": size,
                        "entry_price": float(p.get("avgPrice", 0)),
                        "notional": float(p.get("positionValue", 0)),
                        "pnl": float(p.get("unrealisedPnl", 0)),
                    }
            cursor = r["result"].get("nextPageCursor")
            if not cursor:
                break
        return positions

    def get_signed_size(
        self, symbol: str, positions: dict | None = None
    ) -> float:
        """Signed position: positive = long, negative = short, 0 = flat."""
        if positions is None:
            positions = self.get_positions()
        p = positions.get(symbol)
        if p is None:
            return 0.0
        return p["size"] if p["side"] == "Buy" else -p["size"]

    # ── Prices ────────────────────────────────────────────────────────────

    def get_price(self, symbol: str) -> float:
        """Last price for a single symbol."""
        r = self.client.get_tickers(category="linear", symbol=symbol)
        price = float(r["result"]["list"][0]["lastPrice"])
        self._price_cache[symbol] = price
        return price

    def get_prices(self, symbols: list[str] | None = None) -> dict[str, float]:
        """
        Fetch prices for a list of symbols (or all linear tickers if None).
        Returns {symbol: last_price}.
        """
        r = self.client.get_tickers(category="linear")
        prices: dict[str, float] = {}
        want = set(symbols) if symbols else None
        for item in r["result"]["list"]:
            sym = item["symbol"]
            if want is None or sym in want:
                prices[sym] = float(item["lastPrice"])
        self._price_cache.update(prices)
        return prices

    # ── Leverage ──────────────────────────────────────────────────────────

    def ensure_leverage(self, symbol: str, leverage: int = DEFAULT_LEVERAGE):
        """Set buy/sell leverage for symbol. Idempotent per session."""
        if symbol in self._leverage_done:
            return
        try:
            self.client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage),
            )
        except Exception as e:
            msg = str(e).lower()
            if "leverage not modified" not in msg and "110043" not in msg:
                print(f"  [leverage] {symbol}: {e}")
        self._leverage_done.add(symbol)

    # ── Orders ────────────────────────────────────────────────────────────

    def market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        reduce_only: bool = False,
    ) -> dict:
        """
        Place a market order on linear perpetual.

        Args:
            symbol: Bybit symbol, e.g. 'BTCUSDT'
            side: 'Buy' or 'Sell'
            qty: quantity in base currency (positive)
            reduce_only: True to only reduce existing position
        """
        self.ensure_leverage(symbol)
        params: dict = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
        }
        if reduce_only:
            params["reduceOnly"] = True
        r = self.client.place_order(**params)
        time.sleep(0.25)  # rate-limit buffer
        return r

    def close_position(
        self,
        symbol: str,
        positions: dict | None = None,
    ) -> bool:
        """
        Close entire position for a symbol via market order.
        Returns True if an order was placed.
        """
        if positions is None:
            positions = self.get_positions()
        p = positions.get(symbol)
        if p is None or p["size"] == 0:
            return False
        close_side = "Sell" if p["side"] == "Buy" else "Buy"
        self.market_order(symbol, close_side, p["size"], reduce_only=True)
        return True

    def cancel_all_orders(self, symbol: str | None = None):
        """Cancel all open orders (optionally for one symbol)."""
        kwargs: dict = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            kwargs["symbol"] = symbol
        try:
            self.client.cancel_all_orders(**kwargs)
        except Exception as e:
            print(f"  [cancel] {e}")
