"""Monitoring Agent - Tracks system health, latency, and risk validity."""
import time
from typing import Dict, Any
from datetime import datetime
from app.execution.agents.base_agent import BaseAgent
from app.infra.circuit_breaker import SystemCircuitBreaker
from app.services.position_monitor import PositionMonitor


class MonitoringAgent(BaseAgent):
    """Monitors system health and triggers alerts."""
    
    def __init__(self, circuit_breaker: SystemCircuitBreaker,
                 position_monitor: PositionMonitor,
                 max_latency_ms: float = 5000,
                 max_drawdown_pct: float = 5.0):
        super().__init__("MonitoringAgent")
        self.circuit_breaker = circuit_breaker
        self.position_monitor = position_monitor
        self.max_latency_ms = max_latency_ms
        self.max_drawdown_pct = max_drawdown_pct
        self.health_history = []
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'issues': [],
            'warnings': [],
            'can_continue_trading': True
        }
        
        # Check 1: Circuit breaker status
        cb_health = await self.circuit_breaker.check_system_health()
        if not cb_health.can_trade:
            health_report['issues'].append({
                'type': 'circuit_breaker_open',
                'severity': 'CRITICAL',
                'details': cb_health.reason
            })
            health_report['can_continue_trading'] = False
        
        # Check 2: API latency
        start_time = time.time()
        try:
            await self._test_api_connectivity(context)
            latency_ms = (time.time() - start_time) * 1000
            
            if latency_ms > self.max_latency_ms:
                health_report['warnings'].append({
                    'type': 'high_latency',
                    'latency_ms': latency_ms,
                    'threshold_ms': self.max_latency_ms
                })
        except Exception as e:
            health_report['issues'].append({
                'type': 'api_connectivity_failed',
                'severity': 'HIGH',
                'details': str(e)
            })
            health_report['can_continue_trading'] = False
        
        # Check 3: Position monitor health
        monitored_count = self.position_monitor.get_monitored_count()
        health_report['position_monitor'] = {
            'monitored_positions': monitored_count,
            'metrics': self.position_monitor.get_metrics()
        }
        
        # Check 4: Drawdown check (via risk engine context)
        # CRITICAL FIX: Only block on negative P&L (drawdown), not positive P&L (profit)
        daily_pnl_pct = context.get('daily_pnl_pct', 0)
        current_drawdown_pct = context.get('current_drawdown_pct', 0)
        
        # Use explicit drawdown metric if available, otherwise calculate from P&L
        # Drawdown should only be tracked when P&L is negative
        drawdown_to_check = current_drawdown_pct if current_drawdown_pct != 0 else min(daily_pnl_pct, 0)
        
        if abs(drawdown_to_check) > self.max_drawdown_pct:
            health_report['issues'].append({
                'type': 'excessive_drawdown',
                'severity': 'CRITICAL',
                'drawdown_pct': drawdown_to_check,
                'threshold_pct': self.max_drawdown_pct
            })
            health_report['can_continue_trading'] = False
        
        # Store health history
        self.health_history.append(health_report)
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return health_report
    
    async def _test_api_connectivity(self, context: Dict[str, Any]):
        """Test exchange API connectivity."""
        # Delegate to exchange manager from context if available
        exchange_manager = context.get('exchange_manager')
        if exchange_manager:
            await exchange_manager.fetch_ticker("BTC/USDT")
