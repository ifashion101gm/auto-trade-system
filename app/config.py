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
    
    # Bybit Demo Trading (separate credentials and domain)
    BYBIT_DEMO_API_KEY: Optional[str] = None
    BYBIT_DEMO_API_SECRET: Optional[str] = None
    BYBIT_USE_DEMO_DOMAIN: bool = False  # Use api-demo.bybit.com instead of api.bybit.com
    
    # Bybit Client Configuration
    BYBIT_CLIENT_LIBRARY: str = "ccxt"  # Options: "ccxt" (default), "pybit" (official SDK)
    BYBIT_RATE_LIMIT_ENABLED: bool = True
    BYBIT_RATE_LIMIT_CALLS_PER_SECOND: int = 10  # Bybit default: 10 requests/sec for authenticated endpoints
    BYBIT_CATEGORY: str = "linear"  # Options: "linear", "inverse", "spot", "option"
    BYBIT_RECV_WINDOW: int = 5000  # Request recv_window in milliseconds (default: 5000ms)
    
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
    GOLD_SYMBOL_BYBIT: str = "XAU/USDT:USDT"  # Gold perpetual swap on Bybit Demo
    GOLD_MAX_LEVERAGE: int = 5
    GOLD_RISK_PER_TRADE: float = 0.01
    GOLD_MIN_CONFIDENCE: float = 0.65
    
    # Live Trading Safety Limits
    LIVE_TRADING_MAX_LEVERAGE: int = 3  # Max leverage for live trading (conservative)
    LIVE_TRADING_MAX_POSITION_USD: float = 500.0  # Max position size in USD
    LIVE_TRADING_MIN_BALANCE_USD: float = 100.0  # Minimum balance required
    VALIDATION_MODE_MAX_POSITION_USD: float = 50.0  # Max for validation tests
    
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
    
    # =========================================================================
    # Execution Layer Architecture (New)
    # =========================================================================
    
    # Event Bus Configuration
    EVENT_BUS_MAX_QUEUE_SIZE: int = 10000
    EVENT_BATCH_INTERVAL_MS: int = 100  # Batch high-frequency events
    
    # WebSocket Configuration
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30  # seconds (ping frequency)
    WEBSOCKET_HEARTBEAT_TIMEOUT: int = 45  # seconds (max time without pong)
    WEBSOCKET_RECONNECT_DELAY: int = 2  # initial delay in seconds
    WEBSOCKET_MAX_RECONNECT_DELAY: int = 60  # max delay in seconds
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS: int = 0  # 0 = unlimited retries
    WEBSOCKET_STALE_STREAM_THRESHOLD: int = 120  # seconds without data before forcing reconnect
    WEBSOCKET_JITTER_FACTOR: float = 0.1  # 10% jitter to prevent thundering herd
    
    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60  # seconds
    
    # Rate Limiter Configuration
    RATE_LIMIT_MAX_CALLS: int = 10
    RATE_LIMIT_TIME_WINDOW: float = 1.0  # seconds
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    BASE_RETRY_DELAY: float = 1.0  # seconds
    MAX_RETRY_DELAY: float = 30.0  # seconds
    
    # Position Monitor Configuration
    POSITION_CHECK_INTERVAL: float = 5.0  # seconds
    
    # Reconciliation Configuration
    RECONCILIATION_INTERVAL_SECONDS: int = 120  # Run every 2 minutes
    
    # =========================================================================
    # Risk Management Engine Configuration
    # =========================================================================
    
    # Daily loss and drawdown limits
    RISK_MAX_DAILY_LOSS_PCT: float = 0.03  # 3% daily loss limit
    RISK_MAX_DRAWDOWN_PCT: float = 0.15  # 15% max drawdown
    
    # Position sizing and leverage
    RISK_MAX_POSITION_SIZE_PCT: float = 0.015  # 1.5% per trade
    RISK_MAX_LEVERAGE: int = 5
    
    # Market condition filters
    RISK_VOLATILITY_THRESHOLD: float = 0.8  # ATR-based chaos threshold
    RISK_MAX_SLIPPAGE_PCT: float = 0.002  # 0.2% max slippage
    
    # Cooldown and consecutive loss tracking
    RISK_COOLDOWN_PERIOD_SECONDS: int = 300  # 5 minutes after consecutive losses
    RISK_MAX_CONSECUTIVE_LOSSES: int = 3
    
    # =========================================================================
    # Circuit Breaker Configuration (Enhanced)
    # =========================================================================
    
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5  # Already exists
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60  # Already exists
    CIRCUIT_BREAKER_SLIPPAGE_THRESHOLD: float = 0.005  # 0.5% slippage triggers breaker
    CIRCUIT_BREAKER_LATENCY_THRESHOLD_MS: float = 5000  # 5s API latency
    CIRCUIT_BREAKER_SPREAD_THRESHOLD_PCT: float = 0.005  # 0.5% spread
    CIRCUIT_BREAKER_SYNC_TOLERANCE_PCT: float = 0.01  # 1% position sync tolerance
    CIRCUIT_BREAKER_WEBSOCKET_STALE_THRESHOLD: int = 120  # seconds
    
    # =========================================================================
    # Order Execution Engine Configuration (Steps 9-12)
    # =========================================================================
    
    # Order Idempotency & Retry
    ORDER_IDEMPOTENCY_ENABLED: bool = True
    ORDER_RETRY_MAX_ATTEMPTS: int = 3
    ORDER_RETRY_BASE_DELAY: float = 1.0
    ORDER_RETRY_MAX_DELAY: float = 30.0
    
    # Reconciliation
    POSITION_SYNC_INTERVAL: int = 5  # seconds
    EMERGENCY_SYNC_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

settings = Settings()
