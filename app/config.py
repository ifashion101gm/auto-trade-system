"""
Centralized configuration management using Pydantic Settings.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/vmassit"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_EVENT_CHANNEL_PREFIX: str = "trading:"
    
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
    ACTIVE_EXCHANGE: str = "mexc"
    
    # Execution Mode: proposal, semi-auto, fully-auto
    EXECUTION_MODE: str = "semi-auto"
    
    # Hybrid Execution Threshold (USD)
    # In semi-auto mode, positions ≤ this value auto-execute
    AUTO_EXECUTE_THRESHOLD_USD: float = 100.0
    
    # Gold Futures Trading Configuration
    GOLD_SYMBOL_BINANCE: str = "PAXG/USDT"  # Paxos Gold on Binance Testnet (legacy)
    GOLD_SYMBOL_MEXC: str = "GOLD(XAUT)/USDT"  # Tether Gold on MEXC Futures (primary)
    GOLD_MAX_LEVERAGE: int = 5
    GOLD_RISK_PER_TRADE: float = 0.01
    GOLD_MIN_CONFIDENCE: float = 0.65
    
    # Trading Profile Configuration
    TRADING_PROFILE: str = "safer_growth"  # Options: safer_growth, aggressive
    
    # Safer Growth Mode (Conservative)
    SAFER_GROWTH_RISK_PER_TRADE: float = 0.005  # 0.5%
    SAFER_GROWTH_MAX_DAILY_DRAWDOWN: float = 0.02  # 2%
    SAFER_GROWTH_MAX_POSITIONS: int = 2
    SAFER_GROWTH_CONFIDENCE_THRESHOLD: float = 0.74
    SAFER_GROWTH_LONDON_BREAKOUT_PRIORITY: bool = True
    SAFER_GROWTH_ATR_STOPS: bool = True
    SAFER_GROWTH_ADAPTIVE_SIZING: bool = True
    
    # Aggressive Mode
    AGGRESSIVE_RISK_PER_TRADE: float = 0.01  # 1%
    AGGRESSIVE_MAX_DAILY_DRAWDOWN: float = 0.04  # 4%
    AGGRESSIVE_MAX_POSITIONS: int = 4
    AGGRESSIVE_CONFIDENCE_THRESHOLD: float = 0.65
    AGGRESSIVE_SCALING_ENTRIES: bool = True
    
    # General
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

settings = Settings()
