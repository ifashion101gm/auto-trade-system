"""
OpenRouter LLM Client for AI sub-agents.
Provides unified access to multiple LLM models via OpenRouter API.
Maps specific models to sub-agents based on complexity and latency requirements.
"""
import httpx
import json
from typing import Dict, Any, Optional, List
from app.config import settings


class OpenRouterClient:
    """
    OpenRouter API client for LLM inference.
    
    Model Mapping Strategy:
    - Regime Detection: Fast, cheap models (low latency)
    - Strategy Selection: Balanced performance/cost
    - Risk Assessment: High accuracy models (complex reasoning)
    """
    
    # Model mapping by agent type - OPTIMIZED FOR COST
    MODEL_MAPPING = {
        'regime_detection': {
            'model': 'openai/gpt-4o-mini',  # Fast, cheap for simple classification
            'max_tokens': 500,
            'temperature': 0.1
        },
        'strategy_selection': {
            'model': 'openai/gpt-4o-mini',  # Cost-effective for strategy selection
            'max_tokens': 1000,
            'temperature': 0.3
        },
        'risk_assessment': {
            'model': 'openai/gpt-4o',  # GPT-4o for high accuracy risk assessment (kept)
            'max_tokens': 1500,
            'temperature': 0.2
        },
        # Smart routing models
        'smart_routing_claude': {
            'model': 'anthropic/claude-3.5-sonnet',  # Only for high uncertainty
            'max_tokens': 2000,
            'temperature': 0.2
        },
        'smart_routing_gpt4o_mini': {
            'model': 'openai/gpt-4o-mini',  # Default for normal cases
            'max_tokens': 1000,
            'temperature': 0.3
        }
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://auto-trade-system.local",
            "X-Title": "Auto Trade System"
        }
        
        print("✅ OpenRouter Client initialized")
    
    async def _make_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Make request to OpenRouter API.
        
        Args:
            model: Model identifier
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Response data
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return result
    
    async def detect_regime(self, market_data: Dict[str, Any]) -> str:
        """
        Detect market regime using fast LLM.
        
        Args:
            market_data: Market indicators
            
        Returns:
            Regime classification: 'Low-vol', 'Normal', or 'High-vol'
        """
        config = self.MODEL_MAPPING['regime_detection']
        
        prompt = f"""
Analyze the following market data and classify the current regime:

Market Data:
- Current Price: ${market_data.get('current_price', 'N/A')}
- Volatility: {market_data.get('volatility', 'N/A')}
- Volume (24h): {market_data.get('volume_24h', 'N/A')}
- Price Change (24h): {market_data.get('price_change_24h', 'N/A')}%

Classify into one of three regimes:
1. Low-vol: Low volatility, stable prices, low volume
2. Normal: Moderate volatility, typical trading patterns
3. High-vol: High volatility, rapid price movements, high volume

Respond with ONLY the regime name (Low-vol, Normal, or High-vol).
"""
        
        messages = [
            {"role": "system", "content": "You are a market regime detection expert."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await self._make_request(
                model=config['model'],
                messages=messages,
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
            
            regime = result['choices'][0]['message']['content'].strip()
            
            # Validate response
            valid_regimes = ['Low-vol', 'Normal', 'High-vol']
            if regime not in valid_regimes:
                # Try to extract valid regime from response
                for valid in valid_regimes:
                    if valid.lower() in regime.lower():
                        return valid
                return 'Normal'  # Default fallback
            
            return regime
            
        except Exception as e:
            print(f"⚠️  OpenRouter regime detection failed: {e}")
            # Fallback to heuristic
            volatility = market_data.get('volatility', 0.5)
            if volatility < 0.3:
                return "Low-vol"
            elif volatility > 0.7:
                return "High-vol"
            else:
                return "Normal"
    
    async def select_strategy(self, market_data: Dict[str, Any], regime: str = "Normal") -> Dict[str, Any]:
        """
        Select optimal trading strategy using balanced LLM.
        
        Args:
            market_data: Market indicators
            regime: Current market regime
            
        Returns:
            Strategy selection with confidence and parameters
        """
        config = self.MODEL_MAPPING['strategy_selection']
        
        prompt = f"""
Based on the market conditions, select the optimal trading strategy.

Market Regime: {regime}

Market Data:
- Symbol: {market_data.get('symbol', 'BTC/USDT')}
- Current Price: ${market_data.get('current_price', 'N/A')}
- RSI: {market_data.get('rsi', 'N/A')}
- MACD: {market_data.get('macd', 'N/A')}
- Moving Average (20): {market_data.get('ma_20', 'N/A')}
- Moving Average (50): {market_data.get('ma_50', 'N/A')}

Available Strategies:
1. momentum: Follow strong price trends (best in Normal/High-vol)
2. mean_reversion: Trade price reversals (best in Low-vol)
3. breakout: Trade breakouts from consolidation (best in Low-vol → Normal transitions)

Select ONE strategy and provide:
- strategy: strategy name
- confidence: confidence score (0.0 to 1.0)
- reason: brief explanation

Respond in JSON format only.
"""
        
        messages = [
            {"role": "system", "content": "You are a trading strategy expert. Respond in JSON format only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await self._make_request(
                model=config['model'],
                messages=messages,
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
            
            content = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON response
            try:
                strategy_data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback parsing
                strategy_data = {
                    'strategy': 'momentum',
                    'confidence': 0.7,
                    'reason': 'Fallback selection'
                }
            
            # Ensure required fields
            strategy_data.setdefault('strategy', 'momentum')
            strategy_data.setdefault('confidence', 0.5)
            strategy_data.setdefault('parameters', {})
            
            return strategy_data
            
        except Exception as e:
            print(f"⚠️  OpenRouter strategy selection failed: {e}")
            # Fallback to heuristic
            return {
                'strategy': 'momentum',
                'confidence': 0.6,
                'parameters': {'lookback_period': 20, 'threshold': 0.02}
            }
    
    async def assess_risk(self, position: Dict[str, Any], market_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Assess risk for proposed position using high-accuracy LLM.
        
        Args:
            position: Proposed trade details
            market_data: Optional market context
            
        Returns:
            Risk assessment with recommendations
        """
        config = self.MODEL_MAPPING['risk_assessment']
        
        prompt = f"""
Assess the risk for the following proposed trade position.

Proposed Position:
- Strategy: {position.get('strategy', 'N/A')}
- Side: {position.get('side', 'N/A')}
- Entry Price: ${position.get('entry_price', 'N/A')}
- Confidence: {position.get('confidence', 'N/A')}

Market Context:
{json.dumps(market_data, indent=2) if market_data else 'Not provided'}

Provide risk assessment with:
- risk_level: 'low', 'medium', or 'high'
- max_position_size: maximum position size in USD
- stop_loss: stop-loss percentage (e.g., 0.02 for 2%)
- leverage_recommendation: recommended leverage (1-10)
- reasoning: brief explanation

Respond in JSON format only.
"""
        
        messages = [
            {"role": "system", "content": "You are a risk management expert. Respond in JSON format only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await self._make_request(
                model=config['model'],
                messages=messages,
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
            
            content = result['choices'][0]['message']['content'].strip()
            
            # Parse JSON response
            try:
                risk_data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback parsing
                risk_data = {
                    'risk_level': 'medium',
                    'max_position_size': 1000,
                    'stop_loss': 0.02,
                    'leverage_recommendation': 2
                }
            
            # Ensure required fields
            risk_data.setdefault('risk_level', 'medium')
            risk_data.setdefault('max_position_size', 1000)
            risk_data.setdefault('stop_loss', 0.02)
            risk_data.setdefault('leverage_recommendation', 2)
            
            return risk_data
            
        except Exception as e:
            print(f"⚠️  OpenRouter risk assessment failed: {e}")
            # Fallback to heuristic
            return {
                'risk_level': 'medium',
                'max_position_size': 1000,
                'stop_loss': 0.02,
                'leverage_recommendation': 2
            }
    
    async def test_connection(self) -> bool:
        """
        Test OpenRouter API connection.
        
        Returns:
            True if connection successful
        """
        try:
            # Simple test request using cost-effective model
            result = await self._make_request(
                model='openai/gpt-4o-mini',
                messages=[{"role": "user", "content": "Say 'OK'"}],
                max_tokens=10,
                temperature=0.1
            )
            
            return True
        except Exception as e:
            print(f"❌ OpenRouter connection test failed: {e}")
            return False
    
    async def smart_routing_assessment(
        self,
        market_data: Dict[str, Any],
        uncertainty_score: float,
        pnl_drawdown: float,
        drawdown_threshold: float = 0.05
    ) -> Dict[str, Any]:
        """
        Smart routing: Use Claude only when needed, otherwise use GPT-4o-mini.
        
        Args:
            market_data: Current market conditions
            uncertainty_score: Model uncertainty (0-1)
            pnl_drawdown: Current P&L drawdown percentage
            drawdown_threshold: Threshold to trigger Claude usage
            
        Returns:
            Decision with selected model and reasoning
        """
        # Determine which model to use based on conditions
        if uncertainty_score > 0.75 or pnl_drawdown > drawdown_threshold:
            # High uncertainty or significant drawdown - use Claude
            config = self.MODEL_MAPPING['smart_routing_claude']
            model_type = 'claude'
            reason = f"High uncertainty ({uncertainty_score:.2f}) or drawdown ({pnl_drawdown:.2%})"
        else:
            # Normal conditions - use GPT-4o-mini for cost savings
            config = self.MODEL_MAPPING['smart_routing_gpt4o_mini']
            model_type = 'gpt-4o-mini'
            reason = f"Normal conditions (uncertainty: {uncertainty_score:.2f}, drawdown: {pnl_drawdown:.2%})"
        
        prompt = f"""
Provide trading decision based on market conditions.

Market Data:
{json.dumps(market_data, indent=2)}

Uncertainty Score: {uncertainty_score}
P&L Drawdown: {pnl_drawdown:.2%}

Provide:
- action: 'BUY', 'SELL', or 'HOLD'
- confidence: 0.0 to 1.0
- position_size_usd: recommended position size
- stop_loss_pct: stop loss percentage
- reasoning: brief explanation

Respond in JSON format only.
"""
        
        messages = [
            {"role": "system", "content": "You are a trading decision expert. Respond in JSON format only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await self._make_request(
                model=config['model'],
                messages=messages,
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
            
            content = result['choices'][0]['message']['content'].strip()
            
            try:
                decision = json.loads(content)
            except json.JSONDecodeError:
                decision = {
                    'action': 'HOLD',
                    'confidence': 0.5,
                    'position_size_usd': 500,
                    'stop_loss_pct': 0.02,
                    'reasoning': 'Fallback decision'
                }
            
            decision['model_used'] = model_type
            decision['routing_reason'] = reason
            
            return decision
            
        except Exception as e:
            print(f"⚠️  Smart routing assessment failed: {e}")
            return {
                'action': 'HOLD',
                'confidence': 0.5,
                'position_size_usd': 500,
                'stop_loss_pct': 0.02,
                'reasoning': f'Error: {str(e)}',
                'model_used': 'fallback',
                'routing_reason': 'Error fallback'
            }
