import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("CWD:", os.getcwd())
print("BINANCE_API_KEY from os:", os.getenv('BINANCE_API_KEY'))

from app.config import settings

print("\n✅ Configuration loaded successfully!")
print(f"Database URL: {settings.DATABASE_URL[:30]}...")
print(f"Redis URL: {settings.REDIS_URL}")
print(f"Active Exchange: {settings.ACTIVE_EXCHANGE}")
print(f"Execution Mode: {settings.EXECUTION_MODE}")
print(f"Binance Testnet: {settings.BINANCE_TESTNET}")
print(f"MEXC API Key configured: {bool(settings.MEXC_API_KEY)}")
print(f"Telegram Bot Token configured: {bool(settings.TELEGRAM_BOT_TOKEN)}")
