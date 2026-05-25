import time
import logging
import requests
from typing import List, Dict, Any, Optional
from config.settings import COINGECKO_API_KEY

logger = logging.getLogger(__name__)

class CoinGeckoClient:
    """
    Resilient CoinGecko API Client featuring exponential backoff retries 
    to robustly bypass rate limitations (HTTP 429).
    """
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        self.session = requests.Session()
        if COINGECKO_API_KEY:
            self.session.headers.update({"x-cg-demo-api-key": COINGECKO_API_KEY})

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        max_retries = 5
        backoff_factor = 2

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=15)
                
                # Check for rate-limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))
                    sleep_time = max(retry_after, backoff_factor ** attempt)
                    logger.warning(f"Rate limited by CoinGecko (429). Retrying in {sleep_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    logger.critical(f"CoinGecko request failed completely for endpoint: {endpoint}")
                    return None
                time.sleep(backoff_factor ** attempt)
        
        return None

    def get_asset_market_data(self, coingecko_ids: List[str]) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches active simple market stats (price, cap, supply) for watch assets.
        """
        ids_str = ",".join(coingecko_ids)
        params = {
            "vs_currencies": "usd",
            "ids": ids_str,
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_last_updated_at": "true"
        }
        raw_data = self._request("simple/price", params=params)
        
        if not raw_data:
            return None

        # Format output to a standard list
        formatted_list = []
        for cg_id, stats in raw_data.items():
            formatted_list.append({
                "coingecko_id": cg_id,
                "current_price": stats.get("usd"),
                "current_market_cap": stats.get("usd_market_cap"),
                "volume_24h": stats.get("usd_24h_vol"),
                "last_updated_at": stats.get("last_updated_at")
            })
        return formatted_list

    def get_hourly_ohlcv(self, coingecko_id: str) -> Optional[List[List[float]]]:
        """
        Retrieves historical hourly OHLCV metrics for an asset.
        Returns a list of ticks: [timestamp_ms, open, high, low, close]
        """
        params = {
            "vs_currency": "usd",
            "days": "1"  # Returns hourly values for 1-90 days range
        }
        # Note: CoinGecko's /ohlc endpoint returns 30-min data for 1 day, hourly for others. 
        # We query 1 day, which provides 30-min/1-hour steps.
        return self._request(f"coins/{coingecko_id}/ohlc", params=params)
