"""
Centralized configuration management using Pydantic Settings.
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional

# Load .env file before initializing settings
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/vmassit.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Trading API
    TRADING_API_SECRET: Optional[str] = None
    
    # LLM Providers
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    
    # OpenRouter (Unified LLM API)
    OPENROUTER_API_KEY: Optional[str] = None
    
    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    
    # Binance Trading (Testnet/Mainnet)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    BINANCE_PAPER_API_KEY: Optional[str] = None
    BINANCE_PAPER_API_SECRET: Optional[str] = None
    BINANCE_TESTNET: bool = True  # Default to testnet for safety
    BINANCE_DEMO_MODE: str = "spot_demo"  # Options: spot_demo, futures_demo, testnet
    
    # MEXC Trading (Spot + Futures)
    MEXC_API_KEY: Optional[str] = None
    MEXC_API_SECRET: Optional[str] = None
    MEXC_PAPER_API_KEY: Optional[str] = None
    MEXC_PAPER_API_SECRET: Optional[str] = None
    MEXC_DEFAULT_MARKET_TYPE: str = "futures"  # "spot" or "futures"
    
    # Bybit Trading
    BYBIT_API_KEY: Optional[str] = None
    BYBIT_API_SECRET: Optional[str] = None
    
    # Active Exchange: binance, mexc, bybit
    ACTIVE_EXCHANGE: str = "binance"
    
    # Execution Mode: proposal, semi-auto, fully-auto
    EXECUTION_MODE: str = "semi-auto"
    
    # Hybrid Execution Threshold (USD)
    # In semi-auto mode, positions ≤ this value auto-execute
    AUTO_EXECUTE_THRESHOLD_USD: float = 100.0
    
    # Gold Futures Trading Configuration
    ACTIVE_EXCHANGE: str = "binance"
    GOLD_SYMBOL_BINANCE: str = "PAXG/USDT"  # Paxos Gold on Binance Testnet
    GOLD_SYMBOL_MEXC: str = "XAUT/USDT"     # Tether Gold on MEXC
    GOLD_MAX_LEVERAGE: int = 5
    GOLD_RISK_PER_TRADE: float = 0.01
    GOLD_MIN_CONFIDENCE: float = 0.65
    
    # General
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"
        case_sensitive = True

settings = Settings()
