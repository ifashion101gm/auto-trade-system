"""
Agent Hierarchy Controller (Commander Pattern).

Implements centralized command structure for coordinating all optimized agents:

Hierarchy:
    Commander (Central Orchestrator)
     ├── Market Scanner (Tier 1 - routine scanning)
     ├── Strategy Analyzer (Tier 1/2 - signal generation)
     ├── Risk Manager (Code-based - deterministic)
     ├── Execution Engine (Code-based - deterministic)
     ├── Portfolio Manager (Tier 2 - periodic review)
     └── Learning Agent (Batch mode - nightly)

Optional Premium Layer:
    Claude Supreme Judge (Tier 3 - rare use only)
     • High uncertainty decisions
     • Conflicting signals resolution
     • Regime shift validation

Benefits:
- Clear separation of concerns
- Centralized decision authority
- Easy to add/remove agents
- Simplified debugging and monitoring
"""
import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.ai.optimized_agents import (
    OptimizedAgentRouter,
    DeterministicRiskManager,
    CodeBasedExecutionEngine,
    CodeBasedMonitor,
    EventBasedNewsSentiment,
    BatchLearningAgent
)


class AgentCommander:
    """
    Central commander that orchestrates all trading agents.
    
    Responsibilities:
    - Coordinate agent execution order
    - Aggregate decisions from multiple agents
    - Resolve conflicts using premium tier when needed
    - Maintain system state and health
    - Schedule batch operations
    
    Design Pattern: Commander/Mediator
    """
    
    def __init__(self):
        """Initialize agent hierarchy."""
        # Core agents
        self.router = OptimizedAgentRouter()
        self.risk_manager = DeterministicRiskManager()
        self.execution_engine = CodeBasedExecutionEngine()
        self.monitor = CodeBasedMonitor()
        
        # Specialized agents
        self.news_sentiment = EventBasedNewsSentiment(router=self.router)
        self.learning_agent = BatchLearningAgent(router=self.router)
        
        # System state
        self.system_state = {
            'status': 'initialized',
            'last_cycle_time': None,
            'cycles_completed': 0,
            'active_positions': 0,
            'daily_pnl': 0.0
        }
        
        print("✅ Agent Commander initialized (hierarchical control)")
        print("   Core Agents: Router, Risk, Execution, Monitor")
        print("   Specialized: News (event-based), Learning (batch)")
    
    async def execute_trading_cycle(
        self,
        market_data: Dict[str, Any],
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Execute complete trading cycle with hierarchical control.
        
        Flow:
        1. Scanner finds setups (Tier 1)
        2. Code risk filters (deterministic)
        3. GPT-mini ranks opportunities (Tier 1)
        4. If complex → Claude validates (Tier 3)
        5. Execution by code (deterministic)
        6. Monitoring by metrics (no LLM)
        
        Args:
            market_data: Current market data
            user_id: User identifier
            
        Returns:
            Complete cycle result with all agent outputs
        """
        cycle_start = time.time()
        
        try:
            # Stage 1: Market Scanning (Tier 1 - cheap/fast)
            scan_result = await self._scan_market(market_data)
            
            # Stage 2: Risk Filtering (Code-based - instant)
            risk_result = self._filter_risks(market_data, scan_result)
            
            if not risk_result['approved']:
                return {
                    'status': 'rejected',
                    'reason': risk_result['reason'],
                    'stage': 'risk_filter'
                }
            
            # Stage 3: Strategy Analysis (Tier 1 or Tier 2)
            strategy_result = await self._analyze_strategy(
                market_data,
                scan_result,
                uncertainty=scan_result.get('uncertainty', 0.5)
            )
            
            # Stage 4: Premium Validation (Tier 3 - only if needed)
            if self._needs_premium_validation(strategy_result, market_data):
                validation_result = await self._claude_validate(
                    market_data,
                    strategy_result
                )
                
                if not validation_result['approved']:
                    return {
                        'status': 'rejected',
                        'reason': 'Premium validation failed',
                        'validation': validation_result,
                        'stage': 'premium_check'
                    }
            
            # Stage 5: Execution Decision (Code-based)
            execution_decision = self._make_execution_decision(
                strategy_result,
                risk_result
            )
            
            # Stage 6: Record Metrics (No LLM)
            self.monitor.record_api_call(
                latency_ms=(time.time() - cycle_start) * 1000,
                success=True
            )
            
            # Update system state
            self.system_state['last_cycle_time'] = datetime.utcnow().isoformat()
            self.system_state['cycles_completed'] += 1
            
            return {
                'status': 'completed',
                'decision': execution_decision,
                'strategy': strategy_result,
                'risk': risk_result,
                'cycle_time_ms': (time.time() - cycle_start) * 1000,
                'agents_used': {
                    'scanner': 'tier1',
                    'risk': 'code',
                    'strategy': strategy_result.get('tier_used', 'unknown'),
                    'execution': 'code',
                    'monitor': 'code'
                }
            }
            
        except Exception as e:
            # Record error
            self.monitor.record_api_call(
                latency_ms=(time.time() - cycle_start) * 1000,
                success=False
            )
            
            return {
                'status': 'error',
                'error': str(e),
                'cycle_time_ms': (time.time() - cycle_start) * 1000
            }
    
    async def _scan_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stage 1: Market scanning with Tier 1 model.
        
        Identifies potential setups quickly and cheaply.
        """
        prompt = f"""
        Quick market scan for {market_data.get('symbol', 'unknown')}:
        Price: ${market_data.get('current_price', 0):,.2f}
        RSI: {market_data.get('rsi', 50)}
        Volatility: {market_data.get('volatility', 0)}
        
        Identify any obvious setups (momentum, mean reversion, breakout).
        Keep analysis brief.
        """
        
        result = await self.router.route_request(
            task_type='market_scan',
            messages=[{"role": "user", "content": prompt}],
            uncertainty=0.3,  # Low uncertainty for scanning
            has_conflicting_signals=False,
            is_high_risk=False
        )
        
        return {
            'setups_found': result.get('response', {}).get('setups', []),
            'uncertainty': 0.3,
            'tier_used': result.get('tier'),
            'raw_response': result.get('response')
        }
    
    def _filter_risks(
        self,
        market_data: Dict[str, Any],
        scan_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 2: Risk filtering with deterministic code.
        
        No LLM - pure formula-based checks.
        """
        # Check daily drawdown
        stop_check = self.risk_manager.should_stop_trading()
        
        if stop_check['should_stop']:
            return {
                'approved': False,
                'reason': f"Trading paused: {', '.join(stop_check['reasons'])}"
            }
        
        # Check volatility limits
        volatility = market_data.get('volatility', 0)
        if volatility > 0.1:  # 10% volatility threshold
            return {
                'approved': False,
                'reason': f"Volatility too high: {volatility*100:.1f}%"
            }
        
        return {
            'approved': True,
            'risk_level': 'low' if volatility < 0.03 else 'medium',
            'checks_passed': ['drawdown', 'volatility']
        }
    
    async def _analyze_strategy(
        self,
        market_data: Dict[str, Any],
        scan_result: Dict[str, Any],
        uncertainty: float
    ) -> Dict[str, Any]:
        """
        Stage 3: Strategy analysis with appropriate tier.
        
        Routes to Tier 1 or Tier 2 based on complexity.
        """
        prompt = f"""
        Analyze trading opportunity:
        Symbol: {market_data.get('symbol')}
        Setups: {scan_result.get('setups_found')}
        
        Recommend best strategy and confidence level.
        """
        
        result = await self.router.route_request(
            task_type='strategy_analysis',
            messages=[{"role": "user", "content": prompt}],
            uncertainty=uncertainty,
            has_conflicting_signals=False,
            is_high_risk=False
        )
        
        return {
            'strategy': result.get('response', {}).get('strategy', 'wait'),
            'confidence': result.get('response', {}).get('confidence', 0.5),
            'tier_used': result.get('tier'),
            'raw_response': result.get('response')
        }
    
    def _needs_premium_validation(
        self,
        strategy_result: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> bool:
        """
        Determine if premium Claude validation is needed.
        
        Triggers:
        - High uncertainty (>0.75)
        - Conflicting signals
        - High-risk regime
        - Large position size
        """
        confidence = strategy_result.get('confidence', 1.0)
        uncertainty = 1.0 - confidence
        
        # Check triggers
        if uncertainty > 0.75:
            return True
        
        volatility = market_data.get('volatility', 0)
        if volatility > 0.08:  # High volatility regime
            return True
        
        return False
    
    async def _claude_validate(
        self,
        market_data: Dict[str, Any],
        strategy_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 4: Premium validation with Claude (Tier 3).
        
        Only called when truly needed (<10% of cycles).
        """
        prompt = f"""
        CRITICAL VALIDATION REQUIRED
        
        Strategy Recommendation: {strategy_result.get('strategy')}
        Confidence: {strategy_result.get('confidence')*100:.1f}%
        Market Data: {market_data}
        
        Validate this decision. Should we proceed?
        Consider all risks and potential outcomes.
        """
        
        result = await self.router.route_request(
            task_type='premium_validation',
            messages=[{"role": "user", "content": prompt}],
            uncertainty=0.85,  # Force Tier 3
            has_conflicting_signals=True,
            is_high_risk=True
        )
        
        response = result.get('response', {})
        
        return {
            'approved': response.get('approve', True),
            'reasoning': response.get('reasoning', ''),
            'tier_used': result.get('tier'),
            'override_recommendation': response.get('override')
        }
    
    def _make_execution_decision(
        self,
        strategy_result: Dict[str, Any],
        risk_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 5: Final execution decision (code-based).
        
        Combines strategy recommendation with risk assessment.
        """
        strategy = strategy_result.get('strategy', 'wait')
        confidence = strategy_result.get('confidence', 0)
        
        # Simple decision matrix
        if strategy == 'wait' or confidence < 0.6:
            action = 'hold'
        elif confidence >= 0.8 and risk_result['approved']:
            action = 'execute'
        else:
            action = 'monitor'
        
        return {
            'action': action,
            'strategy': strategy,
            'confidence': confidence,
            'risk_approved': risk_result['approved']
        }
    
    async def run_scheduled_tasks(self):
        """
        Run scheduled batch tasks.
        
        Called by scheduler at specific times:
        - Daily: Learning analysis (00:00 UTC)
        - Weekly: Strategy optimization (Sunday 00:00)
        - Monthly: Deep tuning (1st of month 00:00)
        """
        now = datetime.utcnow()
        
        # Daily learning
        if now.hour == 0 and now.minute == 0:
            print("📊 Running daily learning analysis...")
            result = await self.learning_agent.run_daily_analysis()
            print(f"   Status: {result['status']}")
        
        # Weekly optimization (Sunday)
        if now.weekday() == 6 and now.hour == 0 and now.minute == 0:
            print("🎯 Running weekly strategy optimization...")
            result = await self.learning_agent.run_weekly_optimization()
            print(f"   Status: {result['status']}")
        
        # Monthly tuning (1st of month)
        if now.day == 1 and now.hour == 0 and now.minute == 0:
            print("🔧 Running monthly deep tuning...")
            result = await self.learning_agent.run_monthly_tuning()
            print(f"   Status: {result['status']}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            'commander_state': self.system_state,
            'health_report': self.monitor.get_health_report(),
            'news_events': self.news_sentiment.get_event_summary(),
            'learning_status': self.learning_agent.get_learning_summary(),
            'router_stats': self.router.get_usage_stats()
        }


# Example usage
if __name__ == "__main__":
    print("=" * 80)
    print("AGENT HIERARCHY CONTROLLER DEMO")
    print("=" * 80)
    print()
    
    # Initialize commander
    commander = AgentCommander()
    
    # Simulate trading cycle
    print("\n🔄 Executing Trading Cycle...")
    
    market_data = {
        'symbol': 'BTC/USDT',
        'current_price': 50000,
        'rsi': 45,
        'volatility': 0.025,
        'volume_24h': 1000000000
    }
    
    # This would make actual API calls in production
    print("   Note: Full cycle requires API calls")
    print("   Showing architecture instead...")
    
    # Show system status
    print("\n📊 System Status:")
    status = commander.get_system_status()
    print(f"   Cycles Completed: {status['commander_state']['cycles_completed']}")
    print(f"   System Health: {status['health_report']['system_status']}")
    print(f"   Pending Trades for Learning: {status['learning_status']['pending_trades']}")
    
    print("\n✅ Agent Hierarchy Controller ready!")
    print("   Architecture: Commander → Scanner → Strategy → Risk → Execution")
    print("   Premium Layer: Claude (only when uncertainty > 0.75)")
