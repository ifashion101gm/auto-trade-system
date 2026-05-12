"""
Strategy module - Pluggable strategy architecture with AI filtering.
"""
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_proposal import SignalProposal
from app.strategy.strategy_manager import StrategyManager
from app.strategy.breakout import BreakoutStrategy
from app.strategy.mean_reversion import MeanReversionStrategy
from app.strategy.trend import TrendStrategy
from app.strategy.ai_filter import AIFilter

__all__ = [
    'BaseStrategy',
    'SignalProposal',
    'StrategyManager',
    'BreakoutStrategy',
    'MeanReversionStrategy',
    'TrendStrategy',
    'AIFilter'
]
