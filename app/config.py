"""
Centralized configuration management using Pydantic Settings.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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
    
    # Admin API Key (for enterprise admin routes)
    ADMIN_API_KEY: Optional[str] = None
    
    # Binance Trading (Testnet/Mainnet)
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    BINANCE_PAPER_API_KEY: Optional[str] = None
    BINANCE_PAPER_API_SECRET: Optional[str] = None
    BINANCE_TESTNET: bool = True  # Default to testnet for safety
    BINANCE_DEMO_MODE: str = "spot_demo"  # Options: spot_demo, futures_demo, testnet
    
    # MEXC Trading (Spot + Futures) - DISABLED
    # MEXC_API_KEY: Optional[str] = None
    # MEXC_API_SECRET: Optional[str] = None
    # MEXC_PAPER_API_KEY: Optional[str] = None
    # MEXC_PAPER_API_SECRET: Optional[str] = None
    # MEXC_DEFAULT_MARKET_TYPE: str = "futures"  # "spot" or "futures"
    
    # Bybit Trading
    BYBIT_API_KEY: Optional[str] = None
    BYBIT_API_SECRET: Optional[str] = None
    
    # Bybit Demo Trading (separate credentials and domain)
    BYBIT_DEMO_API_KEY: Optional[str] = None
    BYBIT_DEMO_API_SECRET: Optional[str] = None
    BYBIT_USE_DEMO_DOMAIN: bool = False  # Use api-demo.bybit.com instead of api.bybit.com
    
    # Bybit Client Configuration
    BYBIT_CLIENT_LIBRARY: str = "pybit"  # Required: "pybit" (official SDK) - CCXT does NOT support Demo Trading
    BYBIT_RATE_LIMIT_ENABLED: bool = True
    BYBIT_RATE_LIMIT_CALLS_PER_SECOND: int = 10  # Bybit default: 10 requests/sec for authenticated endpoints
    BYBIT_CATEGORY: str = "linear"  # Options: "linear", "inverse", "spot", "option"
    BYBIT_RECV_WINDOW: int = 5000  # Request recv_window in milliseconds (default: 5000ms)
    
    # Active Exchange: binance, mexc, bybit
    ACTIVE_EXCHANGE: str = "bybit"  # Changed from 'mexc' to 'bybit'
    
    # Execution Mode: proposal, semi-auto, fully-auto
    EXECUTION_MODE: str = "semi-auto"
    
    # Hybrid Execution Threshold (USD)
    # In semi-auto mode, positions ≤ this value auto-execute
    AUTO_EXECUTE_THRESHOLD_USD: float = 100.0
    
    # Gold Futures Trading Configuration - EXCLUSIVE SYMBOL
    GOLD_SYMBOL_BINANCE: str = "XAU/USDT"  # Gold on Binance (legacy)
    GOLD_SYMBOL_MEXC: str = "XAU/USDT"  # Gold on MEXC Futures
    GOLD_SYMBOL_BYBIT: str = "XAUUSDT"  # Gold perpetual swap on Bybit Demo/Live
    
    # Primary Trading Symbol - EXCLUSIVELY XAUUSDT
    PRIMARY_TRADING_SYMBOL: str = "XAUUSDT"  # All trading restricted to this symbol
    ENABLED_TRADING_SYMBOLS: list = ["XAUUSDT"]  # Only XAUUSDT allowed
    
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
    
    # =========================================================================
    # Sprint 5: Micro-Live Trading Parameters (Controlled Capital Deployment)
    # =========================================================================
    
    # Micro-Live Mode Settings (Phase 1: Initial Live Testing)
    MICRO_LIVE_ENABLED: bool = False  # Set to True when ready for micro-live
    MICRO_LIVE_MAX_LEVERAGE: int = 3  # Conservative leverage cap
    MICRO_LIVE_RISK_PER_TRADE: float = 0.005  # 0.5% per trade
    MICRO_LIVE_DAILY_LOSS_LIMIT: float = 0.01  # 1% daily loss limit
    MICRO_LIVE_MAX_POSITION_USD: float = 20.0  # $20 max position size
    MICRO_LIVE_MAX_CONCURRENT_POSITIONS: int = 2  # Max 2 open positions
    MICRO_LIVE_MIN_CONFIDENCE_THRESHOLD: float = 0.75  # Higher confidence required
    
    # Scale-Up Phases Configuration
    SCALE_UP_PHASE_1_CAPITAL_USD: float = 100.0  # Micro-Live starting capital
    SCALE_UP_PHASE_2_CAPITAL_USD: float = 500.0  # 50% scale (after validation)
    SCALE_UP_FULL_DEPLOYMENT_CAPITAL_USD: float = 1000.0  # Full deployment
    
    # Phase Transition Criteria
    PHASE_TRANSITION_MIN_TRADES: int = 50  # Minimum trades before phase-up
    PHASE_TRANSITION_MIN_WIN_RATE: float = 0.55  # 55% win rate required
    PHASE_TRANSITION_MAX_DRAWDOWN: float = 0.05  # Max 5% drawdown allowed
    PHASE_TRANSITION_MIN_PROFIT_FACTOR: float = 1.5  # Profit factor requirement
    PHASE_TRANSITION_VALIDATION_DAYS: int = 7  # Minimum days in current phase
    
    # Emergency Stop Configuration
    EMERGENCY_STOP_ENABLED: bool = True
    EMERGENCY_STOP_DAILY_LOSS_PCT: float = 0.02  # Auto-stop at -2%
    EMERGENCY_STOP_MAX_SLIPPAGE_PCT: float = 0.01  # Auto-stop if slippage >1%
    EMERGENCY_STOP_INFRASTRUCTURE_FAILURES: int = 3  # Consecutive failures trigger stop
    
    # Alert Thresholds
    ALERT_DAILY_LOSS_WARNING_PCT: float = -0.02  # Warn at -2%
    ALERT_DAILY_LOSS_CRITICAL_PCT: float = -0.03  # Critical at -3%
    ALERT_SLIPPAGE_WARNING_PCT: float = 0.003  # 0.3%
    ALERT_SLIPPAGE_CRITICAL_PCT: float = 0.005  # 0.5%
    ALERT_LATENCY_WARNING_MS: float = 2000  # 2 seconds
    ALERT_LATENCY_CRITICAL_MS: float = 5000  # 5 seconds
    ALERT_FILL_RATE_WARNING_PCT: float = 95.0  # Below 95%
    ALERT_WEBSOCKET_RECONNECT_THRESHOLD: int = 5  # Per hour
    
    # General
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # =========================================================================
    # Phase 2: Self-Healing Watchdog Configuration
    # =========================================================================
    
    # API Watchdog
    API_WATCHDOG_MAX_LATENCY_MS: float = 5000
    API_WATCHDOG_CHECK_INTERVAL_SEC: int = 30
    API_WATCHDOG_FAILURE_THRESHOLD: int = 3
    
    # Database Watchdog
    DB_WATCHDOG_MAX_POOL_UTILIZATION_PCT: float = 80.0
    DB_WATCHDOG_STALE_TRANSACTION_THRESHOLD_SEC: int = 300
    DB_WATCHDOG_CHECK_INTERVAL_SEC: int = 60
    
    # Memory Watchdog
    MEMORY_WATCHDOG_WARNING_THRESHOLD_MB: float = 512
    MEMORY_WATCHDOG_CRITICAL_THRESHOLD_MB: float = 1024
    MEMORY_WATCHDOG_GC_TRIGGER_THRESHOLD_MB: float = 768
    MEMORY_WATCHDOG_CHECK_INTERVAL_SEC: int = 120
    
    # Queue Watchdog
    QUEUE_WATCHDOG_MAX_TASK_AGE_SEC: int = 300
    QUEUE_WATCHDOG_MAX_QUEUE_DEPTH: int = 100
    QUEUE_WATCHDOG_CHECK_INTERVAL_SEC: int = 60
    
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
    RECONCILIATION_INTERVAL_SECONDS: int = 120  # Run every 2 minutes (Issue B)
    RECONCILIATION_AUTO_REPAIR_SAFE: bool = True  # Auto-repair safe mismatches
    RECONCILIATION_TELEGRAM_ALERTS: bool = True  # Enable Telegram alerts for critical mismatches
    RECONCILIATION_PROMETHEUS_METRICS: bool = True  # Publish metrics to Prometheus
    RECONCILIATION_MAX_ORPHANED_AGE_HOURS: int = 24  # Max age before flagging orphaned orders
    RECONCILIATION_GHOST_POSITION_ACTION: str = "import_and_alert"  # Options: import_and_alert, alert_only, ignore
    
    # =========================================================================
    # Risk Management Engine Configuration
    # =========================================================================
    
    # Daily loss and drawdown limits
    RISK_MAX_DAILY_LOSS_PCT: float = 0.03  # 3% daily loss limit
    RISK_MAX_DRAWDOWN_PCT: float = 0.15  # 15% max drawdown
    RISK_STATE_FILE: str = '.risk_state.json'
    KILL_SWITCH_STATE_FILE: str = '.kill_switch_state.json'
    
    # Position sizing and leverage
    RISK_MAX_POSITION_SIZE_PCT: float = 0.015  # 1.5% per trade
    RISK_MAX_LEVERAGE: int = 5
    
    # Market condition filters
    RISK_VOLATILITY_THRESHOLD: float = 0.8  # ATR-based chaos threshold
    RISK_MAX_SLIPPAGE_PCT: float = 0.002  # 0.2% max slippage
    
    # Cooldown and consecutive loss tracking
    RISK_COOLDOWN_PERIOD_SECONDS: int = 300  # 5 minutes after consecutive losses
    RISK_MAX_CONSECUTIVE_LOSSES: int = 3
    
    # Concurrent position limits
    RISK_MAX_CONCURRENT_POSITIONS: int = Field(
        default=3,
        description="Maximum number of concurrent open positions"
    )
    
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
