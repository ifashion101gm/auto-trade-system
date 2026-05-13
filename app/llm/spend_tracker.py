"""
LLM Spend Cap Enforcement - Budget guardrails and cost control.
Prevents runaway token costs through real-time tracking and automatic degradation.

Features:
- Real-time spend tracking (per request, hourly, daily, weekly)
- Automatic model downgrade when approaching limits
- Telegram alerts for budget warnings
- Hard caps that block non-critical requests
- Cost-aware routing decisions
"""
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from app.config import settings
from app.logging_config import get_logger
from app.notifications.notifier import TelegramNotifier

logger = get_logger(__name__)


class SpendTracker:
    """Track LLM spending across multiple time windows."""
    
    def __init__(
        self,
        daily_limit: float = None,
        weekly_limit: float = None,
        monthly_limit: float = None
    ):
        """
        Initialize spend tracker.
        
        Args:
            daily_limit: Daily spend limit in USD
            weekly_limit: Weekly spend limit in USD
            monthly_limit: Monthly spend limit in USD
        """
        self.daily_limit = daily_limit or getattr(settings, 'LLM_DAILY_SPEND_LIMIT', 10.0)
        self.weekly_limit = weekly_limit or getattr(settings, 'LLM_WEEKLY_SPEND_LIMIT', 50.0)
        self.monthly_limit = monthly_limit or getattr(settings, 'LLM_MONTHLY_SPEND_LIMIT', 200.0)
        
        # Cost tracking
        self.current_daily_spend = 0.0
        self.current_weekly_spend = 0.0
        self.current_monthly_spend = 0.0
        
        # Token tracking
        self.daily_token_count = 0
        self.weekly_token_count = 0
        
        # Request counting
        self.daily_request_count = 0
        self.weekly_request_count = 0
        
        # Time tracking
        self.last_reset_time = datetime.now(timezone.utc)
        self.today = self.last_reset_time.date()
        self.this_week_start = self._get_week_start(self.last_reset_time)
        self.this_month_start = self.last_reset_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Per-request cost tracking
        self.cost_per_1k_tokens = {
            'gpt-4o-mini': 0.00015,  # $0.15 per 1M tokens
            'gpt-4o': 0.0025,  # $2.50 per 1M tokens
            'claude-3.5-sonnet': 0.003,  # $3.00 per 1M tokens
            'gemini-pro': 0.0005,  # $0.50 per 1M tokens
        }
        
        logger.info(f"✅ SpendTracker initialized")
        logger.info(f"   Daily limit: ${self.daily_limit:.2f}")
        logger.info(f"   Weekly limit: ${self.weekly_limit:.2f}")
        logger.info(f"   Monthly limit: ${self.monthly_limit:.2f}")
    
    def _get_week_start(self, dt: datetime) -> datetime:
        """Get start of current week (Monday)."""
        start = dt - timedelta(days=dt.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _check_and_reset_windows(self):
        """Check if we need to reset any time windows."""
        now = datetime.now(timezone.utc)
        
        # Reset daily if new day
        if now.date() > self.today:
            logger.info(f"📊 Daily spend reset: ${self.current_daily_spend:.4f} spent yesterday")
            self.current_daily_spend = 0.0
            self.daily_token_count = 0
            self.daily_request_count = 0
            self.today = now.date()
        
        # Reset weekly if new week
        current_week_start = self._get_week_start(now)
        if current_week_start > self.this_week_start:
            logger.info(f"📊 Weekly spend reset: ${self.current_weekly_spend:.4f} spent last week")
            self.current_weekly_spend = 0.0
            self.weekly_token_count = 0
            self.weekly_request_count = 0
            self.this_week_start = current_week_start
        
        # Reset monthly if new month
        if now.month > self.this_month_start.month or now.year > self.this_month_start.year:
            logger.info(f"📊 Monthly spend reset: ${self.current_monthly_spend:.4f} spent last month")
            self.current_monthly_spend = 0.0
            self.this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    def calculate_cost(self, model: str, token_count: int) -> float:
        """
        Calculate cost for a request.
        
        Args:
            model: Model name
            token_count: Number of tokens used
        
        Returns:
            Cost in USD
        """
        cost_per_token = self.cost_per_1k_tokens.get(model, 0.001) / 1000  # Default $1 per 1M
        return token_count * cost_per_token
    
    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        agent_type: str = 'unknown'
    ):
        """
        Record LLM usage and update spend tracking.
        
        Args:
            model: Model used
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            agent_type: Type of agent making request
        """
        self._check_and_reset_windows()
        
        total_tokens = prompt_tokens + completion_tokens
        cost = self.calculate_cost(model, total_tokens)
        
        # Update counters
        self.current_daily_spend += cost
        self.current_weekly_spend += cost
        self.current_monthly_spend += cost
        
        self.daily_token_count += total_tokens
        self.weekly_token_count += total_tokens
        
        self.daily_request_count += 1
        self.weekly_request_count += 1
        
        logger.debug(
            f"💰 LLM usage: {model} | "
            f"Tokens: {total_tokens} (prompt={prompt_tokens}, completion={completion_tokens}) | "
            f"Cost: ${cost:.6f} | "
            f"Daily: ${self.current_daily_spend:.4f}/{self.daily_limit:.2f}"
        )
    
    def check_budget_status(self) -> Dict[str, Any]:
        """
        Check current budget status and determine allowed actions.
        
        Returns:
            Budget status with recommendations
        """
        self._check_and_reset_windows()
        
        # Calculate percentages
        daily_pct = self.current_daily_spend / self.daily_limit if self.daily_limit > 0 else 0
        weekly_pct = self.current_weekly_spend / self.weekly_limit if self.weekly_limit > 0 else 0
        monthly_pct = self.current_monthly_spend / self.monthly_limit if self.monthly_limit > 0 else 0
        
        # Determine degradation level
        if daily_pct >= 1.0 or weekly_pct >= 1.0 or monthly_pct >= 1.0:
            degradation_level = 'BLOCK_ALL'
        elif daily_pct >= 0.90 or weekly_pct >= 0.90:
            degradation_level = 'HEURISTIC_ONLY'
        elif daily_pct >= 0.75 or weekly_pct >= 0.75:
            degradation_level = 'DOWNGRADE_TO_MINI'
        elif daily_pct >= 0.50:
            degradation_level = 'WARNING'
        else:
            degradation_level = 'NORMAL'
        
        return {
            'degradation_level': degradation_level,
            'daily': {
                'spent': round(self.current_daily_spend, 4),
                'limit': self.daily_limit,
                'percentage': round(daily_pct * 100, 2),
                'remaining': round(max(0, self.daily_limit - self.current_daily_spend), 4)
            },
            'weekly': {
                'spent': round(self.current_weekly_spend, 4),
                'limit': self.weekly_limit,
                'percentage': round(weekly_pct * 100, 2),
                'remaining': round(max(0, self.weekly_limit - self.current_weekly_spend), 4)
            },
            'monthly': {
                'spent': round(self.current_monthly_spend, 4),
                'limit': self.monthly_limit,
                'percentage': round(monthly_pct * 100, 2),
                'remaining': round(max(0, self.monthly_limit - self.current_monthly_spend), 4)
            },
            'can_use_premium_models': degradation_level in ['NORMAL', 'WARNING'],
            'can_use_any_llm': degradation_level != 'BLOCK_ALL',
            'should_alert': daily_pct >= 0.80 or weekly_pct >= 0.80
        }
    
    def should_block_request(self, agent_type: str = 'non-critical') -> bool:
        """
        Determine if request should be blocked based on budget.
        
        Args:
            agent_type: Type of agent ('critical' or 'non-critical')
        
        Returns:
            True if request should be blocked
        """
        status = self.check_budget_status()
        degradation = status['degradation_level']
        
        # Block all if at limit
        if degradation == 'BLOCK_ALL':
            return True
        
        # Block non-critical if severely over budget
        if degradation == 'HEURISTIC_ONLY' and agent_type != 'critical':
            return True
        
        return False
    
    def get_recommended_model(self, requested_model: str) -> str:
        """
        Get recommended model based on budget status.
        
        Args:
            requested_model: Originally requested model
        
        Returns:
            Downgraded model if necessary
        """
        status = self.check_budget_status()
        degradation = status['degradation_level']
        
        if degradation == 'HEURISTIC_ONLY':
            return 'heuristic'  # No LLM, use rules
        elif degradation == 'DOWNGRADE_TO_MINI':
            # Downgrade premium models to mini
            if requested_model in ['gpt-4o', 'claude-3.5-sonnet']:
                return 'gpt-4o-mini'
        elif degradation == 'WARNING':
            # Just log warning, no downgrade yet
            pass
        
        return requested_model
    
    async def send_budget_alert(
        self,
        notifier: TelegramNotifier,
        status: Dict[str, Any]
    ):
        """
        Send Telegram alert for budget warnings.
        
        Args:
            notifier: Telegram notifier instance
            status: Budget status from check_budget_status()
        """
        if not status.get('should_alert'):
            return
        
        degradation = status['degradation_level']
        daily = status['daily']
        weekly = status['weekly']
        
        message = (
            f"⚠️ **LLM Budget Alert**\n\n"
            f"**Status:** {degradation}\n\n"
            f"**Daily Spend:** ${daily['spent']:.4f} / ${daily['limit']:.2f} ({daily['percentage']}%)\n"
            f"**Weekly Spend:** ${weekly['spent']:.4f} / ${weekly['limit']:.2f} ({weekly['percentage']}%)\n\n"
        )
        
        if degradation == 'BLOCK_ALL':
            message += "🚨 **ALL LLM CALLS BLOCKED** - Budget exceeded!\n"
        elif degradation == 'HEURISTIC_ONLY':
            message += "⚠️ Only heuristic mode available (no LLM calls)\n"
        elif degradation == 'DOWNGRADE_TO_MINI':
            message += "⬇️ Premium models downgraded to GPT-4o-mini\n"
        else:
            message += "ℹ️ Approaching budget limits\n"
        
        await notifier.send_message(message)
        logger.warning(f"Budget alert sent: {degradation}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive spend metrics."""
        self._check_and_reset_windows()
        
        return {
            'current_daily_spend': round(self.current_daily_spend, 4),
            'current_weekly_spend': round(self.current_weekly_spend, 4),
            'current_monthly_spend': round(self.current_monthly_spend, 4),
            'daily_token_count': self.daily_token_count,
            'weekly_token_count': self.weekly_token_count,
            'daily_request_count': self.daily_request_count,
            'weekly_request_count': self.weekly_request_count,
            'limits': {
                'daily': self.daily_limit,
                'weekly': self.weekly_limit,
                'monthly': self.monthly_limit
            }
        }
