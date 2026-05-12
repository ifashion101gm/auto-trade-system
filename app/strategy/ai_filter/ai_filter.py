"""
AI Filter - Validates signals from technical strategies using LLM analysis.

Purpose:
- Filter low-confidence signals from technical strategies
- Add contextual awareness (news sentiment, market regime shifts)
- Adjust confidence scores based on multi-factor analysis

Note: Currently uses rule-based filtering. Can be enhanced with LLM integration later.
"""
from typing import Dict, Any, Optional
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger

logger = get_logger(__name__)

class AIFilter:
    """AI-powered signal validation layer."""
    
    def __init__(self, use_openrouter: bool = False, min_confidence_threshold: float = 0.6):
        self.use_openrouter = use_openrouter
        self.min_confidence_threshold = min_confidence_threshold
        # TODO: Initialize ModelRouter when available
        # self.router = ModelRouter() if use_openrouter else None
        self.router = None
    
    async def validate_signal(self, signal: SignalProposal, 
                              market_context: Dict[str, Any]) -> Optional[SignalProposal]:
        """
        Validate and potentially adjust signal confidence using AI.
        
        Args:
            signal: Raw signal from technical strategy
            market_context: Additional context (news, sentiment, volatility)
            
        Returns:
            Validated signal with adjusted confidence, or None if filtered out
        """
        try:
            # If confidence already below threshold, reject immediately
            if signal.confidence < self.min_confidence_threshold:
                logger.info(f"Signal rejected: confidence {signal.confidence} below threshold")
                return None
            
            # If no AI router, apply rule-based validation
            if not self.router:
                logger.debug("No AI router available, applying rule-based validation")
                return self._rule_based_validation(signal, market_context)
            
            # TODO: Implement LLM-based validation when ModelRouter is available
            # For now, pass through with original confidence
            logger.debug("LLM validation not yet implemented, passing signal through")
            return signal
            
        except Exception as e:
            logger.error(f"AI filter error: {e}. Passing signal through.")
            return signal  # Fail-safe: pass through on error
    
    def _rule_based_validation(self, signal: SignalProposal, 
                               market_context: Dict[str, Any]) -> Optional[SignalProposal]:
        """
        Apply rule-based validation as fallback when AI is not available.
        
        Rules:
        - Reject if confidence too low
        - Reduce confidence in high volatility regimes for mean reversion
        - Boost confidence for trend strategies in strong trends
        """
        validated_confidence = signal.confidence
        regime = market_context.get('regime', 'Normal')
        volatility = market_context.get('volatility', 0.5)
        
        # Adjust confidence based on strategy-regime compatibility
        if signal.strategy_name == 'mean_reversion' and regime == 'High-vol':
            # Mean reversion performs poorly in high volatility
            validated_confidence *= 0.8
            logger.debug(f"Reduced confidence for mean_reversion in high volatility")
        
        elif signal.strategy_name == 'trend' and regime == 'Low-vol':
            # Trend following needs volatility
            validated_confidence *= 0.85
            logger.debug(f"Reduced confidence for trend in low volatility")
        
        elif signal.strategy_name == 'breakout' and volatility > 0.03:
            # Breakouts work well with higher volatility
            validated_confidence = min(0.95, validated_confidence * 1.1)
            logger.debug(f"Boosted confidence for breakout in high volatility")
        
        # Check if still above threshold after adjustments
        if validated_confidence < self.min_confidence_threshold:
            logger.info(f"Signal filtered by rules: adjusted confidence {validated_confidence:.2f}")
            return None
        
        # Update signal with validated confidence
        signal.confidence = round(validated_confidence, 2)
        signal.metadata['rule_validated'] = True
        signal.metadata['original_confidence'] = signal.confidence
        
        logger.info(f"Signal validated by rules: confidence {signal.confidence}")
        return signal
    
    def _build_validation_prompt(self, signal: SignalProposal, 
                                 market_context: Dict[str, Any]) -> str:
        """Build prompt for AI validation (for future LLM integration)."""
        return f"""
Validate this trading signal:

Signal Details:
- Strategy: {signal.strategy_name}
- Symbol: {signal.symbol}
- Side: {signal.side}
- Entry: ${signal.entry_price:,.2f}
- Stop Loss: ${signal.stop_loss:,.2f}
- Take Profit: ${signal.take_profit:,.2f}
- Original Confidence: {signal.confidence:.2f}
- Indicators: {signal.indicators}

Market Context:
- Regime: {market_context.get('regime', 'Unknown')}
- Volatility: {market_context.get('volatility', 'N/A')}
- Volume Trend: {market_context.get('volume_trend', 'N/A')}

Respond with JSON:
{{
  "approve": true/false,
  "validated_confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}
"""
