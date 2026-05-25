import logging
import requests
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

class BinanceClient:
    """
    Binance Spot API client designed to query orderbook limits, 
    calculating depth within 1% price deviations.
    """
    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        self.session = requests.Session()

    def get_order_book_depth(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves bid/ask depth values and calculates standard spreads.
        Uses USDT trading pairs (e.g., BTCUSDT).
        """
        # Ensure symbol matches Binance format
        binance_symbol = f"{symbol}USDT"
        if symbol == "USDT":
            return None # Skip self-pairing
        
        url = f"{self.BASE_URL}/depth"
        params = {"symbol": binance_symbol, "limit": 100}

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            bids = data.get("bids", [])
            asks = data.get("asks", [])

            if not bids or not asks:
                return None

            # Best bid/ask for spread calculation
            best_bid = Decimal(bids[0][0])
            best_ask = Decimal(asks[0][0])
            mid_price = (best_bid + best_ask) / Decimal("2.0")
            spread_percentage = ((best_ask - best_bid) / mid_price) * Decimal("100.0")

            # Calculate 1% dynamic thresholds
            bid_threshold = mid_price * Decimal("0.99")
            ask_threshold = mid_price * Decimal("1.01")

            bid_depth_1pct = Decimal("0.0")
            ask_depth_1pct = Decimal("0.0")

            # Accumulate bid quantity within 1% of mid-price
            for price_str, qty_str in bids:
                price = Decimal(price_str)
                qty = Decimal(qty_str)
                if price >= bid_threshold:
                    bid_depth_1pct += qty * price  # Value in USDT
                else:
                    break  # Bids are sorted DESC, so we can stop early

            # Accumulate ask quantity within 1% of mid-price
            for price_str, qty_str in asks:
                price = Decimal(price_str)
                qty = Decimal(qty_str)
                if price <= ask_threshold:
                    ask_depth_1pct += qty * price  # Value in USDT
                else:
                    break  # Asks are sorted ASC, so we can stop early

            return {
                "symbol": symbol,
                "mid_price": float(mid_price),
                "bid_depth_1pct": float(bid_depth_1pct),
                "ask_depth_1pct": float(ask_depth_1pct),
                "spread_percentage": float(spread_percentage)
            }

        except Exception as e:
            logger.error(f"Failed to fetch orderbook depth from Binance for {binance_symbol}: {e}")
            return None
