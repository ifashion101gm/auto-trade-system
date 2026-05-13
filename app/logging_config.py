"""
Production-grade logging configuration using Loguru.

Provides structured, rotating logs with context injection for:
- Trade lifecycle audit trails
- Error debugging with full stack traces
- System health monitoring
- WebSocket connectivity tracking

Features:
- Console output with colored, human-readable format (development)
- File output with daily rotation and 30-day retention (production)
- JSON structured logging for log aggregation (Loki/Promtail)
- Automatic context injection (trade_id, symbol, order_id, session_id)
- PII-safe logging (API keys/secrets masked)
- Separate log files by severity level
"""
import sys
import os
from pathlib import Path
from loguru import logger
from app.config import settings


# ============================================================================
# Log Directory Setup
# ============================================================================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# ============================================================================
# Custom Log Format for Console (Human-Readable, Colored)
# ============================================================================

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# ============================================================================
# Custom Log Format for Files (Detailed with Context)
# ============================================================================

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{extra[session_id]: <10} | "
    "{extra[symbol]: <12} | "
    "{extra[trade_id]: <10} | "
    "{extra[order_id]: <15} | "
    "{message}"
)

# Set default values for extra fields to avoid KeyError
logger.configure(patcher=lambda record: record["extra"].setdefault("session_id", ""))
logger.configure(patcher=lambda record: record["extra"].setdefault("symbol", ""))
logger.configure(patcher=lambda record: record["extra"].setdefault("trade_id", ""))
logger.configure(patcher=lambda record: record["extra"].setdefault("order_id", ""))

# ============================================================================
# JSON Format for Log Aggregation (Loki/Promtail Compatible)
# ============================================================================

JSON_FORMAT = "{message}"


def json_serializer(record):
    """
    Serialize log record to JSON format for structured logging.
    
    Args:
        record: Loguru log record
        
    Returns:
        JSON string representation of log record
    """
    import json
    
    # Extract standard fields
    log_entry = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "logger": record["name"],
        "module": record["file"].name,
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
        "session_id": record["extra"].get("session_id", ""),
        "symbol": record["extra"].get("symbol", ""),
        "trade_id": record["extra"].get("trade_id", ""),
        "order_id": record["extra"].get("order_id", ""),
    }
    
    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
            "traceback": record["exception"].traceback if record["exception"].traceback else None,
        }
    
    return json.dumps(log_entry, default=str)


def mask_sensitive_data(message: str) -> str:
    """
    Mask sensitive data (API keys, secrets) in log messages.
    
    Args:
        message: Original log message
        
    Returns:
        Message with sensitive data masked
    """
    import re
    
    # Mask API keys (common patterns)
    message = re.sub(r'api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9]{20,}', 'api_key=***MASKED***', message, flags=re.IGNORECASE)
    message = re.sub(r'secret["\']?\s*[:=]\s*["\']?[A-Za-z0-9]{20,}', 'secret=***MASKED***', message, flags=re.IGNORECASE)
    message = re.sub(r'token["\']?\s*[:=]\s*["\']?[A-Za-z0-9]{20,}', 'token=***MASKED***', message, flags=re.IGNORECASE)
    
    # Mask long alphanumeric strings that look like keys
    message = re.sub(r'\b[A-Za-z0-9]{32,}\b', '***KEY_MASKED***', message)
    
    return message


class LoguruFilter:
    """Custom filter to mask sensitive data before logging."""
    
    def __call__(self, record):
        """Filter and mask sensitive data in log records."""
        record["message"] = mask_sensitive_data(str(record["message"]))
        return True


# ============================================================================
# Logger Configuration
# ============================================================================

def setup_logger():
    """
    Configure Loguru logger with multiple sinks (outputs).
    
    Sinks:
    1. Console: Colored, human-readable (DEBUG level for development)
    2. File (all.log): All logs with daily rotation, 30-day retention
    3. File (error.log): ERROR and above only
    4. File (trades.log): Trade-specific logs only
    5. File (json.log): JSON structured logs for Loki aggregation
    """
    
    # Remove default handler
    logger.remove()
    
    # Get log level from settings
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO').upper()
    
    # ------------------------------------------------------------------------
    # Sink 1: Console Output (Colored, Human-Readable)
    # ------------------------------------------------------------------------
    logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=False,  # Don't show variable values in production
        filter=LoguruFilter(),
    )
    
    # ------------------------------------------------------------------------
    # Sink 2: All Logs File (Daily Rotation, 30-Day Retention)
    # ------------------------------------------------------------------------
    logger.add(
        LOG_DIR / "all_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="DEBUG",
        rotation="00:00",  # Rotate at midnight
        retention="30 days",
        compression="zip",  # Compress old logs
        enqueue=True,  # Thread-safe async logging
        backtrace=True,
        diagnose=False,
        filter=LoguruFilter(),
        serialize=False,
    )
    
    # ------------------------------------------------------------------------
    # Sink 3: Error Logs Only (Separate file for quick debugging)
    # ------------------------------------------------------------------------
    logger.add(
        LOG_DIR / "error_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="ERROR",
        rotation="00:00",
        retention="90 days",  # Keep errors longer for auditing
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True,  # Show full diagnostics for errors
        filter=LoguruFilter(),
    )
    
    # ------------------------------------------------------------------------
    # Sink 4: Trade-Specific Logs (Audit Trail)
    # ------------------------------------------------------------------------
    logger.add(
        LOG_DIR / "trades_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="INFO",
        rotation="00:00",
        retention="365 days",  # Keep trade logs for 1 year (compliance)
        compression="zip",
        enqueue=True,
        filter=lambda record: any(keyword in record["message"].lower() for keyword in [
            'trade', 'order', 'position', 'pnl', 'entry', 'exit', 
            'signal', 'strategy', 'risk'
        ]),
    )
    
    # ------------------------------------------------------------------------
    # Sink 5: JSON Structured Logs (For Loki/Promtail Aggregation)
    # ------------------------------------------------------------------------
    logger.add(
        LOG_DIR / "json_{time:YYYY-MM-DD}.log",
        format=JSON_FORMAT,
        level="INFO",
        rotation="00:00",
        retention="7 days",
        compression="zip",
        enqueue=True,
        serialize=json_serializer,
        filter=LoguruFilter(),
    )
    
    # ------------------------------------------------------------------------
    # Sink 6: WebSocket Events (Connectivity Monitoring)
    # ------------------------------------------------------------------------
    logger.add(
        LOG_DIR / "websocket_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="INFO",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        enqueue=True,
        filter=lambda record: any(keyword in record["message"].lower() for keyword in [
            'websocket', 'ws', 'connect', 'disconnect', 'reconnect',
            'heartbeat', 'subscription', 'stream'
        ]),
    )
    
    logger.info(f"✅ Logging configured: level={log_level}, dir={LOG_DIR.absolute()}")
    logger.debug(f"   - Console: {log_level}")
    logger.debug(f"   - all_*.log: DEBUG, 30-day retention")
    logger.debug(f"   - error_*.log: ERROR+, 90-day retention")
    logger.debug(f"   - trades_*.log: INFO (trade-only), 365-day retention")
    logger.debug(f"   - json_*.log: INFO (structured), 7-day retention")
    logger.debug(f"   - websocket_*.log: INFO (WS-only), 30-day retention")


# ============================================================================
# Context Manager for Trade/Order Context Injection
# ============================================================================

from contextlib import contextmanager
from typing import Optional
import uuid


@contextmanager
def trade_context(
    trade_id: Optional[str] = None,
    symbol: Optional[str] = None,
    order_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """
    Context manager to inject trading context into log records.
    
    Usage:
        with trade_context(trade_id='123', symbol='BTC/USDT'):
            logger.info("Trade opened")  # Automatically includes trade_id and symbol
    
    Args:
        trade_id: Unique trade identifier
        symbol: Trading pair symbol
        order_id: Order identifier
        session_id: Session identifier (auto-generated if not provided)
    """
    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    
    # Patch logger with context
    ctx_logger = logger.bind(
        trade_id=trade_id or "",
        symbol=symbol or "",
        order_id=order_id or "",
        session_id=session_id,
    )
    
    try:
        yield ctx_logger
    finally:
        # Context automatically cleaned up when exiting 'with' block
        pass


@contextmanager
def order_context(
    order_id: str,
    symbol: str,
    trade_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """
    Context manager for order-specific logging.
    
    Usage:
        with order_context(order_id='ord-123', symbol='ETH/USDT'):
            logger.info("Order submitted")
    
    Args:
        order_id: Order identifier (required)
        symbol: Trading pair symbol (required)
        trade_id: Associated trade ID
        session_id: Session identifier
    """
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    
    ctx_logger = logger.bind(
        trade_id=trade_id or "",
        symbol=symbol,
        order_id=order_id,
        session_id=session_id,
    )
    
    try:
        yield ctx_logger
    finally:
        pass


# ============================================================================
# Convenience Functions for Common Log Patterns
# ============================================================================

def log_trade_entry(
    trade_id: str,
    symbol: str,
    side: str,
    entry_price: float,
    quantity: float,
    leverage: int,
    stop_loss: float,
    take_profit: float,
    strategy_name: str,
    risk_pct: float,
    order_id: str,
):
    """
    Log standardized trade entry event.
    
    Args:
        trade_id: Unique trade identifier
        symbol: Trading pair
        side: LONG or SHORT
        entry_price: Entry price
        quantity: Position size
        leverage: Leverage multiplier
        stop_loss: Stop loss price
        take_profit: Take profit price
        strategy_name: Strategy that generated signal
        risk_pct: Risk percentage
        order_id: Exchange order ID
    """
    with trade_context(trade_id=trade_id, symbol=symbol, order_id=order_id) as ctx_logger:
        ctx_logger.info(
            f"🟢 TRADE OPENED | Side={side} | Entry=${entry_price:,.2f} | "
            f"Qty={quantity} | Lev={leverage}x | SL=${stop_loss:,.2f} | "
            f"TP=${take_profit:,.2f} | Strategy={strategy_name} | Risk={risk_pct}%"
        )


def log_trade_exit(
    trade_id: str,
    symbol: str,
    exit_price: float,
    pnl: float,
    pnl_pct: float,
    duration: str,
    close_reason: str,
    order_id: str,
):
    """
    Log standardized trade exit event.
    
    Args:
        trade_id: Unique trade identifier
        symbol: Trading pair
        exit_price: Exit price
        pnl: Realized PnL (absolute)
        pnl_pct: Realized PnL (percentage)
        duration: Trade duration (e.g., "2h 15m")
        close_reason: Reason for closing (TP_HIT, SL_HIT, MANUAL, SIGNAL_REVERSAL)
        order_id: Exchange order ID
    """
    emoji = "✅" if pnl > 0 else "❌"
    
    with trade_context(trade_id=trade_id, symbol=symbol, order_id=order_id) as ctx_logger:
        ctx_logger.info(
            f"{emoji} TRADE CLOSED | Exit=${exit_price:,.2f} | "
            f"PnL=${pnl:,.2f} ({pnl_pct:+.2f}%) | Duration={duration} | "
            f"Reason={close_reason}"
        )


def log_api_error(
    error: Exception,
    endpoint: str,
    status_code: Optional[int] = None,
    payload: Optional[dict] = None,
):
    """
    Log API error with full context for debugging.
    
    Args:
        error: Exception object
        endpoint: API endpoint that failed
        status_code: HTTP status code (if available)
        payload: Request payload (sanitized)
    """
    error_type = type(error).__name__
    
    logger.error(
        f"🚨 API ERROR | Endpoint={endpoint} | Status={status_code} | "
        f"Type={error_type} | Message={str(error)}"
    )
    
    if payload:
        # Sanitize payload to remove sensitive data
        sanitized = {k: v for k, v in payload.items() if 'key' not in k.lower() and 'secret' not in k.lower()}
        logger.debug(f"   Payload: {sanitized}")
    
    logger.opt(exception=True).debug("Full traceback:")


def log_websocket_event(
    event: str,
    latency_ms: Optional[float] = None,
    subscriptions: Optional[int] = None,
    attempt_count: Optional[int] = None,
):
    """
    Log WebSocket connectivity event.
    
    Args:
        event: Event type (CONNECTED, DISCONNECTED, RECONNECTING, RECONNECTED)
        latency_ms: Connection latency in milliseconds
        subscriptions: Number of active subscriptions
        attempt_count: Reconnection attempt number
    """
    emoji_map = {
        'CONNECTED': '✅',
        'DISCONNECTED': '⚠️',
        'RECONNECTING': '🔄',
        'RECONNECTED': '✅',
    }
    emoji = emoji_map.get(event.upper(), '📡')
    
    msg = f"{emoji} WEBSOCKET {event.upper()}"
    
    if latency_ms is not None:
        msg += f" | Latency={latency_ms:.1f}ms"
    if subscriptions is not None:
        msg += f" | Subscriptions={subscriptions}"
    if attempt_count is not None:
        msg += f" | Attempt=#{attempt_count}"
    
    logger.info(msg)


def log_sync_result(
    mismatches: int,
    ghost_positions: int,
    repaired: int,
    duration_ms: float,
):
    """
    Log position synchronization result.
    
    Args:
        mismatches: Number of detected mismatches
        ghost_positions: Number of ghost positions found
        repaired: Number of issues auto-repaired
        duration_ms: Sync duration in milliseconds
    """
    if mismatches == 0:
        logger.debug(f"✅ SYNC COMPLETE | Mismatches=0 | Duration={duration_ms:.0f}ms")
    else:
        logger.warning(
            f"⚠️  SYNC ISSUES DETECTED | Mismatches={mismatches} | "
            f"Ghosts={ghost_positions} | Repaired={repaired} | "
            f"Duration={duration_ms:.0f}ms"
        )


# ============================================================================
# Initialize Logger on Module Import
# ============================================================================

setup_logger()

# Export configured logger
__all__ = ['logger', 'trade_context', 'order_context', 
           'log_trade_entry', 'log_trade_exit', 'log_api_error',
           'log_websocket_event', 'log_sync_result']
