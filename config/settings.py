import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment configuration
load_dotenv(BASE_DIR / ".env")

# Database configurations
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = int(os.getenv("DATABASE_PORT", "5432"))
DB_USER = os.getenv("DATABASE_USER", "coindcx_admin")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "supersecure_db_pass_99")
DB_NAME = os.getenv("DATABASE_NAME", "coindcx_intelligence")

# Exchange endpoints config
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")

# Risk limits
VOLATILITY_THRESHOLD = float(os.getenv("VOLATILITY_THRESHOLD", "0.08"))
PRICE_DROP_THRESHOLD = float(os.getenv("PRICE_DROP_THRESHOLD", "0.05"))

# Alert notification credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_RECEIVER_EMAIL = os.getenv("ALERT_RECEIVER_EMAIL", "")

# Asset watch list configuration (standard assets for CoinDCX analysis)
WATCH_LIST = {
    "BTC": {"name": "Bitcoin", "coingecko_id": "bitcoin"},
    "ETH": {"name": "Ethereum", "coingecko_id": "ethereum"},
    "SOL": {"name": "Solana", "coingecko_id": "solana"},
    "MATIC": {"name": "Polygon", "coingecko_id": "matic-network"},
    "WRX": {"name": "WazirX", "coingecko_id": "wazirx"}
}
