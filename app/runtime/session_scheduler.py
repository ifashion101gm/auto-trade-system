"""
Session Scheduler - Manages trading windows for XAUUSDT gold trading.

Gold is most active during:
- London Session Open (high volatility)
- New York Session Open (highest volatility)
- London-NY Overlap (peak liquidity)

This scheduler automatically enables/disables trading based on UTC time windows.
"""
from datetime import datetime, timezone, time as dt_time
from typing import Dict, Any, Optional
from enum import Enum

from app.logging_config import get_logger

logger = get_logger(__name__)


class TradingSession(Enum):
    """Trading session types."""
    LONDON_OPEN = "london_open"
    NY_OPEN = "ny_open"
    LONDON_NY_OVERLAP = "london_ny_overlap"
    OFF_HOURS = "off_hours"


class SessionScheduler:
    """
    Manages trading sessions for gold (XAUUSDT).
    
    Trading Windows (UTC):
    - London Open: 07:50 - 10:30
    - NY Open: 13:20 - 16:30
    - Overlap: 13:20 - 16:30 (both sessions active)
    
    Outside these windows, trading is disabled to avoid:
    - Low liquidity periods
    - Wide spreads
    - Unpredictable price action
    """
    
    def __init__(self):
        """Initialize session scheduler with trading windows."""
        # London session (UTC)
        self.london_start = dt_time(7, 50)
        self.london_end = dt_time(10, 30)
        
        # New York session (UTC)
        self.ny_start = dt_time(13, 20)
        self.ny_end = dt_time(16, 30)
        
        logger.info("✅ SessionScheduler initialized")
        logger.info(f"   London: {self.london_start} - {self.london_end} UTC")
        logger.info(f"   NY: {self.ny_start} - {self.ny_end} UTC")
    
    def get_current_session(self) -> TradingSession:
        """
        Get current trading session.
        
        Returns:
            TradingSession enum value
        """
        now_utc = datetime.now(timezone.utc).time()
        
        # Check if in overlap period (both London and NY active)
        if self.ny_start <= now_utc <= min(self.london_end, self.ny_end):
            return TradingSession.LONDON_NY_OVERLAP
        
        # Check London session
        if self.london_start <= now_utc <= self.london_end:
            return TradingSession.LONDON_OPEN
        
        # Check NY session
        if self.ny_start <= now_utc <= self.ny_end:
            return TradingSession.NY_OPEN
        
        return TradingSession.OFF_HOURS
    
    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed in current session.
        
        Returns:
            True if within active trading window, False otherwise
        """
        session = self.get_current_session()
        return session != TradingSession.OFF_HOURS
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get detailed session information.
        
        Returns:
            Dict with session details
        """
        current = self.get_current_session()
        now_utc = datetime.now(timezone.utc)
        
        # Calculate time until next session
        next_session, time_until = self._get_next_session_info(now_utc)
        
        return {
            "current_session": current.value,
            "trading_allowed": self.is_trading_allowed(),
            "current_time_utc": now_utc.isoformat(),
            "sessions": {
                "london": {
                    "start": str(self.london_start),
                    "end": str(self.london_end),
                    "active": current == TradingSession.LONDON_OPEN
                },
                "new_york": {
                    "start": str(self.ny_start),
                    "end": str(self.ny_end),
                    "active": current == TradingSession.NY_OPEN
                },
                "overlap": {
                    "active": current == TradingSession.LONDON_NY_OVERLAP
                }
            },
            "next_session": {
                "name": next_session.value if next_session else None,
                "starts_in_seconds": int(time_until.total_seconds()) if time_until else None
            }
        }
    
    def _get_next_session_info(self, now: datetime):
        """
        Get information about the next trading session.
        
        Args:
            now: Current datetime
        
        Returns:
            Tuple of (next_session, time_until)
        """
        current_time = now.time()
        today = now.date()
        
        # Define session start times for today
        sessions_today = [
            (TradingSession.LONDON_OPEN, dt_time(7, 50)),
            (TradingSession.NY_OPEN, dt_time(13, 20)),
        ]
        
        # Find next session today
        for session, start_time in sessions_today:
            if current_time < start_time:
                next_dt = datetime.combine(today, start_time, tzinfo=timezone.utc)
                time_until = next_dt - now
                return session, time_until
        
        # If no sessions left today, return tomorrow's London open
        tomorrow = today.replace(day=today.day + 1) if today.day < 28 else \
                   today.replace(month=today.month + 1, day=1) if today.month < 12 else \
                   today.replace(year=today.year + 1, month=1, day=1)
        
        next_dt = datetime.combine(tomorrow, self.london_start, tzinfo=timezone.utc)
        time_until = next_dt - now
        
        return TradingSession.LONDON_OPEN, time_until
    
    def should_reduce_position_size(self) -> bool:
        """
        Check if position size should be reduced (outside peak hours).
        
        Returns:
            True if outside optimal trading hours
        """
        session = self.get_current_session()
        # Reduce size during single sessions, full size during overlap
        return session in [TradingSession.LONDON_OPEN, TradingSession.NY_OPEN]
    
    def get_recommended_leverage(self) -> int:
        """
        Get recommended leverage based on current session.
        
        Returns:
            Recommended leverage (lower outside overlap)
        """
        session = self.get_current_session()
        
        if session == TradingSession.LONDON_NY_OVERLAP:
            return 5  # Higher leverage during high liquidity
        elif session in [TradingSession.LONDON_OPEN, TradingSession.NY_OPEN]:
            return 3  # Moderate leverage
        else:
            return 1  # Minimal leverage or no trading
