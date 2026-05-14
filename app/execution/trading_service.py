"""
Live Trading Service integrating AI decisions with real exchange execution.
Implements complete cycle: Market Data → AI Analysis → Order Execution → Learning
Enhanced with state machine pattern for predictable execution flow.
"""
import asyncio
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.ai_agents.orchestrator import AIAgentOrchestrator
from app.infra.exchange_manager import UnifiedExchangeManager
from app.infra.hybrid_exchange_manager import HybridExchangeManager
from app.notifications.notifier import TelegramNotifier
from app.risk.validator import TradeValidator
from app.risk.risk_engine import RiskEngine
from app.infra.circuit_breaker import SystemCircuitBreaker
from app.database.models import PaperTrades, DecisionJournal, StrategyEvaluations, TradeProposals
from app.learning.param_cache import LearningParameterCache
from app.logging_config import get_logger
from app.execution.states import ExecutionState, is_valid_transition
from app.execution.state_validator import state_validator
from app.events.event_bus import event_bus
from app.execution.self_healing_engine import SelfHealingExecutionEngine

logger = get_logger(__name__)


class LiveTradingService:
    """
    Complete trading service that orchestrates the full trading cycle.
    
    Flow:
    1. Fetch real market data from exchange
    2. Run AI analysis (OpenRouter-powered)
    3. Execute real orders on testnet/mainnet
    4. Persist results to database
    5. Send Telegram notifications
    6. Analyze performance for self-learning
    """
    
    def __init__(
        self,
        exchange_name: Optional[str] = None,
        use_testnet: Optional[bool] = None,
        use_openrouter: bool = True
    ):
        """
        Initialize live trading service.
        
        Args:
            exchange_name: Exchange to use (defaults to ACTIVE_EXCHANGE)
            use_testnet: Use testnet mode (defaults to BINANCE_TESTNET)
            use_openrouter: Use OpenRouter for AI (default: True)
        """
        self.exchange_name = exchange_name or settings.ACTIVE_EXCHANGE
        self.use_testnet = use_testnet if use_testnet is not None else settings.BINANCE_TESTNET
        self.execution_mode = settings.EXECUTION_MODE
        
        # Initialize components
        self.orchestrator = AIAgentOrchestrator(use_openrouter=use_openrouter)
        self.exchange_manager = UnifiedExchangeManager(
            exchange_name=self.exchange_name,
            use_testnet=self.use_testnet
        )
        self.notifier = TelegramNotifier()
        self.validator = TradeValidator()
        self.param_cache = LearningParameterCache()
        
        # Initialize risk engine and circuit breaker
        self.risk_engine = RiskEngine(db_session=None)  # Will be set per request
        self.circuit_breaker = SystemCircuitBreaker(notifier=self.notifier)
        
        # State machine tracking
        self.current_state = ExecutionState.IDLE
        self.state_history: List[Tuple[ExecutionState, datetime]] = []
        
        logger.info("✅ Live Trading Service initialized")
        logger.info(f"   Exchange: {self.exchange_name.upper()} ({'TESTNET' if self.use_testnet else 'LIVE'})")
        logger.info(f"   Mode: {self.execution_mode}")
        logger.info(f"   AI: {'OpenRouter' if use_openrouter else 'Heuristic'}")
        logger.info(f"   State Machine: Enabled")
        
        # Initialize self-healing agents
        from app.services.startup_recovery import StartupRecoveryService
        from app.services.position_monitor import PositionMonitor
        from app.services.reconciliation_service import PositionReconciliationService
        from app.execution.reconciliation_engine import PositionReconciliationEngine
        from app.execution.agents.signal_agent import SignalAgent
        from app.execution.agents.execution_agent import ExecutionAgent
        from app.execution.agents.verification_agent import VerificationAgent
        from app.execution.agents.monitoring_agent import MonitoringAgent
        from app.execution.agents.recovery_agent import RecoveryAgent
        from app.execution.agents.reconciliation_agent import ReconciliationAgent
        
        # Initialize dependencies
        self.position_monitor = PositionMonitor(
            event_bus=event_bus,
            exchange_manager=self.exchange_manager,
            check_interval=5.0
        )
        
        self.reconciliation_service = PositionReconciliationService(
            exchange_manager=self.exchange_manager
        )
        
        self.reconciliation_engine = PositionReconciliationEngine(
            testnet=self.use_testnet
        )
        
        self.startup_recovery = StartupRecoveryService(
            exchange_manager=self.exchange_manager,
            position_monitor=self.position_monitor,
            reconciliation_service=self.reconciliation_service,
            circuit_breaker=self.circuit_breaker,
            event_bus=event_bus,
            notifier=self.notifier
        )
        
        # Initialize agents
        self.signal_agent = SignalAgent(
            orchestrator=self.orchestrator,
            risk_engine=self.risk_engine,
            validator=self.validator
        )
        
        self.execution_agent = ExecutionAgent(
            exchange_manager=self.exchange_manager,
            max_retries=3,
            max_slippage_pct=0.5
        )
        
        self.verification_agent = VerificationAgent(
            exchange_manager=self.exchange_manager
        )
        
        self.monitoring_agent = MonitoringAgent(
            circuit_breaker=self.circuit_breaker,
            position_monitor=self.position_monitor,
            max_latency_ms=5000,
            max_drawdown_pct=5.0
        )
        
        self.recovery_agent = RecoveryAgent(
            startup_recovery=self.startup_recovery,
            event_bus=event_bus
        )
        
        self.reconciliation_agent = ReconciliationAgent(
            reconciliation_service=self.reconciliation_service,
            reconciliation_engine=self.reconciliation_engine
        )
        
        # Initialize self-healing execution engine. Keep direct aliases for
        # backwards-compatible health/reporting code and existing tests.
        self.self_healing_engine = SelfHealingExecutionEngine(
            monitoring_agent=self.monitoring_agent,
            verification_agent=self.verification_agent,
            recovery_agent=self.recovery_agent,
            reconciliation_agent=self.reconciliation_agent,
            circuit_breaker=self.circuit_breaker,
            notifier=self.notifier,
            event_bus=event_bus
        )
        self.dedup_engine = self.self_healing_engine.dedup_engine
        self.anomaly_detector = self.self_healing_engine.anomaly_detector
        
        logger.info("✅ Self-healing execution engine initialized (health gates + dedup + anomaly recovery)")
    
    async def _transition_to(self, new_state: ExecutionState):
        """
        Transition to a new execution state with strict validation.
        
        Args:
            new_state: Target state to transition to
            
        Raises:
            ValueError: If transition is not valid
        """
        old_state = self.current_state
        if old_state == new_state:
            logger.debug(f"State already {new_state.value}; skipping no-op transition")
            return
        
        # Validate transition using state validator (with audit trail)
        state_validator.validate_execution_transition(
            old_state, new_state,
            context=f"LiveTradingService.{old_state.value}"
        )
        
        # Perform transition
        self.current_state = new_state
        self.state_history.append((new_state, datetime.utcnow()))
        
        # Publish state change event (non-blocking)
        try:
            asyncio.create_task(event_bus.publish(
                'STATE_CHANGED',
                {
                    'old_state': old_state.value,
                    'new_state': new_state.value,
                    'timestamp': datetime.utcnow().isoformat()
                },
                priority=15
            ))
        except Exception as e:
            logger.warning(f"Failed to publish state change event: {e}")
        
        logger.info(f"🔄 State transition: {old_state.value} → {new_state.value}")
    
    def get_state_metrics(self) -> Dict[str, Any]:
        """Get state machine metrics."""
        return {
            'current_state': self.current_state.value,
            'total_transitions': len(self.state_history),
            'recent_states': [
                {'state': s.value, 'timestamp': t.isoformat()}
                for s, t in self.state_history[-10:]
            ]
        }
    
    async def execute_trading_cycle(
        self,
        symbol: str = "BTC/USDT",
        user_id: str = "default_user",
        db_session: Optional[AsyncSession] = None,
        execute_on_binance: bool = True,
        execute_on_mexc: bool = False
    ) -> Dict[str, Any]:
        """
        Execute complete trading cycle with real market data and order execution.
        
        Args:
            symbol: Trading pair to analyze
            user_id: User identifier for tracking
            db_session: Database session for persistence
            
        Returns:
            Complete cycle results including order details and P&L
        """
        cycle_start = time.time()
        results = {
            'symbol': symbol,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'failed',
            'stages': {}
        }
        
        try:
            # Pre-cycle self-healing health gate. This checks the monitoring
            # agent and circuit breaker before any market/exchange action.
            await self._transition_to(ExecutionState.IDLE)
            
            health_decision = await self.self_healing_engine.run_preflight({
                'user_id': user_id,
                'db_session': db_session,
                'exchange_manager': self.exchange_manager
            })
            
            if not health_decision.can_continue:
                logger.warning("⚠️ Trading blocked by self-healing health gate")
                results['status'] = health_decision.status
                results['health_issues'] = health_decision.issues
                results['self_healing'] = health_decision.to_dict()
                return results
            
            # Transition: IDLE -> FETCHING_DATA
            await self._transition_to(ExecutionState.FETCHING_DATA)
            
            # Stage 1: Fetch Real Market Data
            logger.info(f"\n📊 Stage 1: Fetching market data for {symbol}...")
            market_data = await self._fetch_market_data(symbol)
            results['stages']['market_data'] = 'success'
            results['market_data'] = market_data
            logger.info(f"   ✅ Current price: ${market_data['current_price']:,.2f}")
            
            # Check market conditions via risk engine
            volatility_check = await self.risk_engine.check_volatility_chaos(symbol)
            if volatility_check:
                logger.warning(f"⚠️  Market volatility too high for {symbol}, skipping trade")
                results['status'] = 'skipped_high_volatility'
                return results
            
            slippage_check = await self.risk_engine.check_slippage_risk(symbol)
            if not slippage_check['approved']:
                logger.warning(f"⚠️  Spread too wide for {symbol}: {slippage_check['spread_pct']:.3%}")
                results['status'] = 'skipped_wide_spread'
                return results
            
            # Transition: FETCHING_DATA -> ANALYZING
            await self._transition_to(ExecutionState.ANALYZING)
            
            # Stage 2: AI Analysis with OpenRouter
            logger.info("\n🧠 Stage 2: Running AI analysis...")
            ai_result = await self.orchestrator.run_paper_trade_cycle(
                market_data=market_data,
                user_id=user_id,
                db_session=db_session
            )
            
            # Handle AI rejection gracefully (not an error, just no trade)
            if ai_result.get('status') == 'rejected':
                reason = ai_result.get('reason', 'Unknown')
                quality_score = ai_result.get('quality_score', 0)
                logger.warning(f"   ⚠️  Trade proposal rejected by quality filter")
                logger.warning(f"      Reason: {reason}")
                logger.warning(f"      Quality Score: {quality_score}/100")
                
                results['stages']['ai_analysis'] = 'rejected'
                results['rejection_reason'] = reason
                results['quality_score'] = quality_score
                results['cycle_time_ms'] = ai_result.get('cycle_time_ms', 0)
                results['status'] = 'rejected'  # Set status to rejected, not failed
                
                # Send rejection notification to Telegram
                # Use the existing notifier instance (singleton ensures shared deduplication state)
                try:
                    await self.notifier.send_trade_rejection_report(
                        symbol=symbol,
                        reason=reason,
                        quality_score=quality_score,
                        cycle_time_ms=results['cycle_time_ms']
                    )
                except Exception as e:
                    logger.error(f"Failed to send rejection report: {e}")
                
                return results
            
            if ai_result.get('status') != 'success':
                error_msg = ai_result.get('error', 'Unknown error')
                raise Exception(f"AI analysis failed: {error_msg}")
            
            results['stages']['ai_analysis'] = 'success'
            results['ai_result'] = ai_result
            logger.info(f"   ✅ Regime: {ai_result['regime']}")
            logger.info(f"   ✅ Strategy: {ai_result['strategy']['strategy']} (confidence: {ai_result['strategy']['confidence']})")
            logger.info(f"   ✅ Risk: {ai_result['risk']['risk_level']}")
            
            # Transition: ANALYZING -> PROPOSING
            await self._transition_to(ExecutionState.PROPOSING)
            
            # Stage 3: Generate Trade Proposal
            proposal = ai_result['trade_proposal']
            logger.info("\n📋 Stage 3: Trade proposal generated")
            logger.info(f"   Side: {proposal['side']}")
            logger.info(f"   Entry: ${proposal['entry_price']:,.2f}")
            logger.info(f"   Stop Loss: ${proposal['stop_loss']:,.2f}")
            logger.info(f"   Take Profit: ${proposal['take_profit']:,.2f}")
            logger.info(f"   Leverage: {proposal['leverage']}x")
            
            # Lifecycle log: Signal generated
            logger.info(
                f"[SIGNAL] {proposal['symbol']} {proposal['side']} @ "
                f"${proposal['entry_price']:,.2f} | "
                f"Confidence: {proposal.get('confidence', 0):.2%}"
            )
            
            # Duplicate signal check
            logger.info("\n🔒 Checking for duplicate signals...")
            signal_decision = await self.self_healing_engine.guard_signal(proposal)
            dedup_result = signal_decision.metadata['deduplication']
            
            if not signal_decision.can_continue:
                logger.warning("⚠️  Duplicate signal detected - rejecting trade")
                results['status'] = signal_decision.status
                results['dedup_hash'] = dedup_result['signal_hash']
                results['self_healing'] = signal_decision.to_dict()
                return results
            
            logger.info(f"   ✅ Signal unique (hash: {dedup_result['signal_hash'][:16]}...)")
            results['dedup_hash'] = dedup_result['signal_hash']
            
            # Transition: PROPOSING -> VALIDATING
            await self._transition_to(ExecutionState.VALIDATING)
            
            # Stage 4: Risk Engine Validation
            logger.info("\n🛡️  Stage 4: Running risk engine validation...")
            risk_decision = await self.risk_engine.check_trade_approval(
                proposal=proposal,
                user_id=user_id
            )
            
            if not risk_decision.approved:
                logger.warning(f"   ❌ Trade rejected by risk engine:")
                for violation in risk_decision.violations:
                    logger.warning(f"      - {violation}")
                
                results['stages']['risk_validation'] = 'rejected'
                results['risk_violations'] = risk_decision.violations
                results['status'] = 'risk_rejected'
                
                # Send rejection notification
                await self.notifier.send_message(
                    f"🚫 Trade Rejected by Risk Engine\n\n"
                    f"Symbol: {symbol}\n"
                    f"Violations:\n" + "\n".join([f"• {v}" for v in risk_decision.violations])
                )
                
                return results
            
            if risk_decision.warnings:
                logger.warning(f"   ⚠️  Risk warnings:")
                for warning in risk_decision.warnings:
                    logger.warning(f"      - {warning}")
            
            results['stages']['risk_validation'] = 'passed'
            results['risk_metrics'] = {
                'daily_pnl_pct': risk_decision.daily_pnl_pct,
                'drawdown_pct': risk_decision.current_drawdown_pct,
                'position_size_pct': risk_decision.position_size_pct,
                'risk_score': risk_decision.risk_score
            }
            
            # Lifecycle log: Risk approved
            logger.info(
                f"[RISK] Approved | Score: {risk_decision.risk_score}/100 | "
                f"Risk: {risk_decision.position_size_pct:.2%}"
            )
            
            # Stage 5: Execute Order (based on execution mode)
            logger.info(f"\n⚡ Stage 5: Executing order (mode: {self.execution_mode})...")
            execution_start = time.time()
            
            try:
                async def _execute_observed_trade():
                    return await self._execute_trade(
                        proposal=proposal,
                        user_id=user_id,
                        db_session=db_session
                    )

                execution_result = await self.self_healing_engine.execute_with_observation(
                    _execute_observed_trade,
                    proposal=proposal,
                    endpoint='create_market_order'
                )
                execution_time_ms = execution_result.get(
                    '_self_healing_latency_ms',
                    (time.time() - execution_start) * 1000
                )

                # Check for anomalies after the engine records execution telemetry.
                if execution_result['status'] == 'executed':
                    anomalies = execution_result.get('_self_healing_anomalies', [])
                    
                    if anomalies:
                        logger.warning("⚠️ Anomalies detected during execution:")
                        for anomaly in anomalies:
                            logger.warning(f"  [{anomaly['severity']}] {anomaly['message']}")
                        
                        results['anomalies'] = anomalies
                        
                        if self.self_healing_engine.should_pause_for_anomalies(anomalies):
                            critical_anomalies = [
                                a for a in anomalies
                                if a['severity'] in self.self_healing_engine.critical_anomaly_severities
                            ]
                            logger.error("🚨 Critical anomalies detected - pausing trading")
                            results['status'] = 'paused_due_to_anomalies'
                            results['critical_anomalies'] = critical_anomalies
                            return results
                
            except Exception:
                raise
            
            results['stages']['execution'] = execution_result['status']
            results['execution'] = execution_result
            
            if execution_result['status'] == 'executed':
                # Post-execution verification and self-healing recovery.
                logger.info("\n🔍 Verifying execution...")
                verification_decision = await self.self_healing_engine.verify_and_recover(
                    execution_result=execution_result,
                    proposal=proposal,
                    context={
                        'user_id': user_id,
                        'db_session': db_session
                    }
                )
                
                results['agents'] = results.get('agents', {})
                results['agents']['verification'] = verification_decision.metadata.get('verification')
                if 'recovery' in verification_decision.metadata:
                    results['agents']['recovery'] = verification_decision.metadata['recovery']
                
                if not verification_decision.can_continue:
                    logger.warning("⚠️ Verification failed and recovery could not fully repair state")
                    results['status'] = verification_decision.status
                    results['self_healing'] = verification_decision.to_dict()
                    return results
                if verification_decision.status != 'verification_passed':
                    results['self_healing'] = verification_decision.to_dict()
                    results['status'] = verification_decision.status
                    return results
                
                # Transition: VALIDATING -> EXECUTING -> MONITORING
                await self._transition_to(ExecutionState.EXECUTING)
                await self._transition_to(ExecutionState.MONITORING)
                
                logger.info(f"   ✅ Order executed: {execution_result.get('order_id')}")
                logger.info(f"   ✅ Filled at: ${execution_result.get('filled_price', 0):,.2f}")
                
                # Stage 5: Send Telegram Notification
                logger.info("\n📱 Stage 5: Sending Telegram notification...")
                await self.notifier.send_trade_entry(execution_result)
                results['stages']['notification'] = 'sent'
                
                # Stage 6: Self-Learning Analysis
                logger.info("\n🎓 Stage 6: Analyzing for self-learning...")
                learning_result = await self._analyze_and_learn(
                    execution_result=execution_result,
                    ai_result=ai_result,
                    db_session=db_session
                )
                results['stages']['learning'] = 'completed'
                results['learning'] = learning_result
            
            # Transition: MONITORING -> IDLE (cycle complete)
            await self._transition_to(ExecutionState.IDLE)
            
            # Post-cycle reconciliation if DB session available
            if db_session:
                logger.info("\n🔄 Running post-cycle reconciliation...")
                try:
                    reconciliation_decision = await self.self_healing_engine.reconcile({
                        'user_id': user_id,
                        'db_session': db_session
                    })
                    reconciliation_result = reconciliation_decision.metadata.get('reconciliation', reconciliation_decision.to_dict())
                    results['agents'] = results.get('agents', {})
                    results['agents']['reconciliation'] = reconciliation_result
                    if not reconciliation_decision.can_continue:
                        results['self_healing_reconciliation'] = reconciliation_decision.to_dict()
                    
                    await self._transition_to(ExecutionState.RECONCILING)
                    await self._transition_to(ExecutionState.IDLE)
                except Exception as recon_error:
                    logger.error(f"Reconciliation failed: {recon_error}")
            
            results['status'] = 'success'
            results['cycle_time_ms'] = (time.time() - cycle_start) * 1000
            
            logger.info(f"\n✅ Trading cycle completed in {results['cycle_time_ms']:.0f}ms")
            return results
            
        except Exception as e:
            # Transition to ERROR state
            try:
                await self._transition_to(ExecutionState.ERROR)
            except:
                pass  # Ignore transition errors during exception handling
            
            results['status'] = 'failed'
            results['error'] = str(e)
            results['cycle_time_ms'] = (time.time() - cycle_start) * 1000
            
            logger.error(f"\n❌ Trading cycle failed: {e}")
            logger.exception("Traceback:")
            
            # Send error notification
            try:
                await self.notifier.send_message(
                    f"🚨 Trading Cycle Failed\n\nSymbol: {symbol}\nError: {str(e)}"
                )
            except:
                pass
            
            return results
    
    async def _fetch_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time market data from exchange.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Market data dictionary with indicators
        """
        # Fetch ticker data
        ticker = await self.exchange_manager.fetch_ticker(symbol)
        
        # Fetch OHLCV for technical indicators
        ohlcv = await self.exchange_manager.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        
        # Calculate basic indicators
        closes = [candle[4] for candle in ohlcv]  # Close prices
        
        # Simple moving averages
        ma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        ma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else closes[-1]
        
        # Volatility (standard deviation of returns)
        returns = [(closes[i] / closes[i-1]) - 1 for i in range(1, len(closes))]
        volatility = (sum(r**2 for r in returns[-20:]) / 20) ** 0.5 if len(returns) >= 20 else 0.5
        
        # RSI calculation (simplified)
        gains = [max(0, r) for r in returns[-14:]]
        losses = [abs(min(0, r)) for r in returns[-14:]]
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 1
        rs = avg_gain / avg_loss if avg_loss != 0 else 1
        rsi = 100 - (100 / (1 + rs))
        
        # Price change 24h
        price_change_24h = ((closes[-1] / closes[0]) - 1) * 100 if len(closes) > 1 else 0
        
        return {
            'symbol': symbol,
            'current_price': ticker['last_price'],
            'bid': ticker['bid'],
            'ask': ticker['ask'],
            'volume_24h': ticker['volume_24h'],
            'high_24h': ticker['high_24h'],
            'low_24h': ticker['low_24h'],
            'price_change_24h': round(price_change_24h, 2),
            'volatility': round(volatility, 4),
            'rsi': round(rsi, 2),
            'ma_20': round(ma_20, 2),
            'ma_50': round(ma_50, 2),
            'macd': round(ma_20 - ma_50, 2),  # Simplified MACD
            'timestamp': ticker['timestamp']
        }
    
    async def _execute_trade(
        self,
        proposal: Dict[str, Any],
        user_id: str,
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Execute trade based on execution mode and position size.
        
        Hybrid Execution Logic:
        - Position ≤ $100 USD: Auto-execute (fully-auto behavior)
        - Position > $100 USD: Require confirmation (semi-auto behavior)
        
        Args:
            proposal: Trade proposal from AI
            user_id: User identifier
            db_session: Database session
            
        Returns:
            Execution result with order details
        """
        symbol = proposal['symbol']
        side = proposal['side'].lower()  # 'buy' or 'sell'
        entry_price = proposal['entry_price']
        quantity = proposal['quantity']
        leverage = proposal['leverage']
        
        # Check minimum balance for live trading
        if not self.use_testnet:
            try:
                balance = await self.exchange_manager.fetch_balance()
                if balance['total_usdt'] < settings.LIVE_TRADING_MIN_BALANCE_USD:
                    error_msg = f"Insufficient balance: ${balance['total_usdt']:.2f} < ${settings.LIVE_TRADING_MIN_BALANCE_USD:.2f}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            except Exception as e:
                logger.warning(f"Could not verify balance: {e}. Proceeding with caution.")
        
        # Calculate position value in USD
        position_value_usd = entry_price * quantity
        
        # Save proposal to database
        if db_session:
            trade_proposal = TradeProposals(
                ts=datetime.utcnow().isoformat(),
                user_id=user_id,
                exchange=self.exchange_name,
                symbol=symbol,
                side=side.upper(),
                entry_price=entry_price,
                stop_loss=proposal.get('stop_loss'),
                take_profit=proposal.get('take_profit'),
                quantity=quantity,
                confidence=proposal.get('confidence'),
                strategy_name=proposal.get('strategy_name'),
                status='pending',
                ai_metadata=json.dumps({
                    'regime': proposal.get('regime'),
                    'risk_level': proposal.get('risk_level'),
                    'position_value_usd': position_value_usd
                })
            )
            db_session.add(trade_proposal)
            await db_session.flush()
            proposal_id = trade_proposal.id
        else:
            proposal_id = None
        
        # Determine execution mode based on position size
        should_auto_execute = False
        
        if self.execution_mode == 'proposal':
            # Validate trade against rules first
            validation = await self.validator.validate_trade(
                proposal=proposal,
                user_id=user_id,
                db_session=db_session,
                exchange=self.exchange_name,
                symbol=symbol
            )
            
            # Send validation report to Telegram
            await self.notifier.send_trade_validation_report(validation, proposal)
            
            if not validation.approved:
                logger.warning(f"Trade REJECTED: {validation.violations}")
                # Update proposal status to rejected
                if db_session and proposal_id:
                    from sqlalchemy import select
                    stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
                    result = await db_session.execute(stmt)
                    prop_record = result.scalar_one_or_none()
                    if prop_record:
                        prop_record.status = 'rejected'
                        await db_session.flush()
                
                return {
                    'status': 'rejected',
                    'proposal_id': proposal_id,
                    'violations': validation.violations,
                    'warnings': validation.warnings,
                    'message': f'Trade rejected: {"; ".join(validation.violations)}',
                    **validation.proposed_trade
                }
            
            if validation.warnings:
                logger.warning(f"Trade approved with warnings: {validation.warnings}")
            
            # Always require manual execution in proposal mode
            return {
                'status': 'proposal_only',
                'proposal_id': proposal_id,
                'message': 'Trade proposal generated. Manual execution required.',
                'position_value_usd': position_value_usd,
                'validation': {
                    'approved': validation.approved,
                    'violations': validation.violations,
                    'warnings': validation.warnings
                },
                **proposal
            }
        
        elif self.execution_mode == 'semi-auto':
            # Validate trade against rules first
            validation = await self.validator.validate_trade(
                proposal=proposal,
                user_id=user_id,
                db_session=db_session,
                exchange=self.exchange_name,
                symbol=symbol
            )
            
            # Send validation report to Telegram
            await self.notifier.send_trade_validation_report(validation, proposal)
            
            if not validation.approved:
                logger.warning(f"Trade REJECTED: {validation.violations}")
                # Update proposal status to rejected
                if db_session and proposal_id:
                    from sqlalchemy import select
                    stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
                    result = await db_session.execute(stmt)
                    prop_record = result.scalar_one_or_none()
                    if prop_record:
                        prop_record.status = 'rejected'
                        await db_session.commit()
                
                return {
                    'status': 'rejected',
                    'proposal_id': proposal_id,
                    'violations': validation.violations,
                    'warnings': validation.warnings,
                    'message': f'Trade rejected: {"; ".join(validation.violations)}',
                    **validation.proposed_trade
                }
            
            if validation.warnings:
                logger.warning(f"Trade approved with warnings: {validation.warnings}")
            
            # HYBRID MODE: Check position size threshold
            AUTO_EXECUTE_THRESHOLD_USD = settings.AUTO_EXECUTE_THRESHOLD_USD
            
            if position_value_usd <= AUTO_EXECUTE_THRESHOLD_USD:
                # Small position: Auto-execute (fully-auto behavior)
                should_auto_execute = True
                logger.info(f"   💰 Position value: ${position_value_usd:.2f} ≤ ${AUTO_EXECUTE_THRESHOLD_USD:.2f}")
                logger.info("   ⚡ Auto-executing (small position)")
            else:
                # Large position: Require confirmation (semi-auto behavior)
                should_auto_execute = False
                logger.info(f"   💰 Position value: ${position_value_usd:.2f} > ${AUTO_EXECUTE_THRESHOLD_USD:.2f}")
                logger.info("   ⏸️  Awaiting confirmation (large position)")
                
                if db_session:
                    await db_session.commit()
                
                return {
                    'status': 'awaiting_confirmation',
                    'proposal_id': proposal_id,
                    'message': f'Proposal saved. Position value ${position_value_usd:.2f} exceeds ${AUTO_EXECUTE_THRESHOLD_USD:.2f} threshold. Call confirm endpoint to execute.',
                    'position_value_usd': position_value_usd,
                    **proposal
                }
        
        elif self.execution_mode == 'fully-auto':
            # Validate trade against rules first
            validation = await self.validator.validate_trade(
                proposal=proposal,
                user_id=user_id,
                db_session=db_session,
                exchange=self.exchange_name,
                symbol=symbol
            )
            
            # Send validation report to Telegram
            await self.notifier.send_trade_validation_report(validation, proposal)
            
            if not validation.approved:
                logger.warning(f"Trade REJECTED: {validation.violations}")
                # Update proposal status to rejected
                if db_session and proposal_id:
                    from sqlalchemy import select
                    stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
                    result = await db_session.execute(stmt)
                    prop_record = result.scalar_one_or_none()
                    if prop_record:
                        prop_record.status = 'rejected'
                        await db_session.commit()
                
                return {
                    'status': 'rejected',
                    'proposal_id': proposal_id,
                    'violations': validation.violations,
                    'warnings': validation.warnings,
                    'message': f'Trade rejected: {"; ".join(validation.violations)}',
                    **validation.proposed_trade
                }
            
            if validation.warnings:
                logger.warning(f"Trade approved with warnings: {validation.warnings}")
            
            # Always auto-execute
            should_auto_execute = True
        
        else:
            raise ValueError(f"Invalid execution mode: {self.execution_mode}")
        
        # Execute order if auto-execution is enabled
        if should_auto_execute:
            try:
                # Validate position size against safety limits
                max_position_usd = (
                    settings.VALIDATION_MODE_MAX_POSITION_USD 
                    if self.use_testnet 
                    else settings.LIVE_TRADING_MAX_POSITION_USD
                )
                
                if position_value_usd > max_position_usd:
                    error_msg = f"Position value ${position_value_usd:.2f} exceeds safety limit ${max_position_usd:.2f}"
                    logger.error(error_msg)
                    
                    # Send alert via Telegram
                    await self.notifier.send_message(
                        f"🚨 SAFETY ALERT: Trade blocked\n{error_msg}\nSymbol: {symbol}\nSide: {side}"
                    )
                    
                    raise ValueError(error_msg)
                
                # Place market order
                order_result = await self.exchange_manager.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    leverage=leverage
                )
                
                # Lifecycle log: Order sent
                logger.info(
                    f"[ORDER_SENT] {symbol} {side.upper()} {quantity} | "
                    f"Order: {order_result.get('order_id')}"
                )
                
                # Update proposal status
                if db_session and proposal_id:
                    stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
                    result = await db_session.execute(stmt)
                    prop_record = result.scalar_one_or_none()
                    if prop_record:
                        prop_record.status = 'executed'
                        await db_session.flush()
                
                # Create paper trade record
                filled_price = order_result.get('price') or entry_price
                fee = order_result.get('fee', {})
                fee_cost = fee.get('cost', 0)
                
                trade_record = PaperTrades(
                    ts_open=datetime.utcnow().isoformat(),
                    user_id=user_id,
                    exchange=self.exchange_name,
                    symbol=symbol,
                    side=side.upper(),
                    leverage=leverage,
                    qty=quantity,
                    entry_price=filled_price,
                    exit_price=None,
                    stop_loss=proposal.get('stop_loss'),
                    take_profit=proposal.get('take_profit'),
                    profit=None,
                    profit_pct=None,
                    status='open',
                    notes=f"Order ID: {order_result['order_id']}, Fee: ${fee_cost:.4f}, Position: ${position_value_usd:.2f}",
                    execution_mode='auto' if position_value_usd <= 100 else 'fully-auto'
                )
                
                if db_session:
                    db_session.add(trade_record)
                    await db_session.commit()
                
                # Lifecycle log: Position opened
                logger.info(
                    f"[POSITION_OPEN] Trade ID: {trade_record.id} | "
                    f"Symbol: {trade_record.symbol} | Side: {trade_record.side}"
                )
                
                return {
                    'status': 'executed',
                    'order_id': order_result['order_id'],
                    'filled_price': filled_price,
                    'filled_quantity': order_result.get('filled', quantity),
                    'fee': fee_cost,
                    'fee_currency': fee.get('currency', 'USDT'),
                    'proposal_id': proposal_id,
                    'trade_id': trade_record.id if db_session else None,
                    'position_value_usd': position_value_usd,
                    'auto_executed': position_value_usd <= 100,
                    **proposal
                }
                
            except Exception as e:
                # Mark proposal as failed
                if db_session and proposal_id:
                    stmt = select(TradeProposals).where(TradeProposals.id == proposal_id)
                    result = await db_session.execute(stmt)
                    prop_record = result.scalar_one_or_none()
                    if prop_record:
                        prop_record.status = 'failed'
                        await db_session.commit()
                
                raise Exception(f"Order execution failed: {str(e)}")
        
        else:
            raise ValueError(f"Invalid execution mode: {self.execution_mode}")
    
    async def _analyze_and_learn(
        self,
        execution_result: Dict[str, Any],
        ai_result: Dict[str, Any],
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Analyze trade execution and update learning parameters.
        
        This implements the self-learning feedback loop by:
        1. Recording execution quality metrics
        2. Analyzing historical performance
        3. Adjusting strategy parameters based on results
        
        Args:
            execution_result: Results from order execution
            ai_result: AI analysis results
            db_session: Database session
            
        Returns:
            Learning analysis results
        """
        # Extract key metrics
        regime = ai_result.get('regime', 'Unknown')
        strategy = ai_result.get('strategy', {}).get('strategy', 'Unknown')
        confidence = ai_result.get('strategy', {}).get('confidence', 0.5)
        risk_level = ai_result.get('risk', {}).get('risk_level', 'medium')
        
        filled_price = execution_result.get('filled_price', 0)
        entry_price = execution_result.get('entry_price', 0)
        
        # Calculate slippage
        slippage_pct = abs(filled_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
        
        # Get current learning parameters
        params = self.param_cache.load_parameters()
        
        # Performance analysis logic
        learning_insights = {
            'regime': regime,
            'strategy': strategy,
            'confidence_used': confidence,
            'risk_level': risk_level,
            'slippage_pct': round(slippage_pct, 4),
            'execution_quality': 'good' if slippage_pct < 0.1 else 'fair' if slippage_pct < 0.5 else 'poor',
            'recommendations': []
        }
        
        # Adaptive parameter adjustment based on performance
        recommendations = []
        
        # Adjust confidence threshold based on regime performance
        if regime == 'High-vol' and confidence < 0.7:
            recommendations.append("Increase confidence threshold in high volatility regimes")
        
        # Adjust position sizing based on risk level
        if risk_level == 'high' and params.get('risk_per_trade', 0.01) > 0.01:
            recommendations.append("Reduce risk per trade in high-risk scenarios")
        
        # Adjust leverage based on execution quality
        if slippage_pct > 0.5:
            recommendations.append("Consider reducing leverage due to high slippage")
        
        learning_insights['recommendations'] = recommendations
        
        # Log learning event to database
        if db_session:
            decision_entry = DecisionJournal(
                ts=datetime.utcnow().isoformat(),
                user_id=execution_result.get('user_id', 'system'),
                prompt=json.dumps({
                    'type': 'learning_feedback',
                    'execution_result': execution_result,
                    'slippage_pct': slippage_pct
                }),
                reply=json.dumps(learning_insights),
                task_type='self_learning_analysis'
            )
            db_session.add(decision_entry)
            await db_session.flush()
        
        logger.info(f"   📊 Slippage: {slippage_pct:.4f}%")
        logger.info(f"   📊 Execution Quality: {learning_insights['execution_quality']}")
        if recommendations:
            logger.info("   💡 Recommendations:")
            for rec in recommendations:
                logger.info(f"      - {rec}")
        
        return learning_insights
    
    async def close_position(
        self,
        trade_id: int,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Close an open position and calculate P&L.
        
        Args:
            trade_id: Paper trade ID to close
            db_session: Database session
            
        Returns:
            Closure result with P&L calculation
        """
        # Fetch trade record
        stmt = select(PaperTrades).where(PaperTrades.id == trade_id)
        result = await db_session.execute(stmt)
        trade = result.scalar_one_or_none()
        
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")
        
        if trade.status != 'open':
            raise ValueError(f"Trade {trade_id} is already closed")
        
        # Get current market price
        ticker = await self.exchange_manager.fetch_ticker(trade.symbol)
        exit_price = ticker['last_price']
        
        # Close position on exchange
        side = 'sell' if trade.side == 'LONG' else 'buy'
        closure_order = await self.exchange_manager.create_market_order(
            symbol=trade.symbol,
            side=side,
            amount=trade.qty,
            leverage=trade.leverage
        )
        
        # Calculate P&L
        if trade.side == 'LONG':
            profit = (exit_price - trade.entry_price) * trade.qty
        else:
            profit = (trade.entry_price - exit_price) * trade.qty
        
        profit_pct = (profit / (trade.entry_price * trade.qty)) * 100
        
        # Update trade record
        trade.ts_close = datetime.utcnow().isoformat()
        trade.exit_price = exit_price
        trade.profit = profit
        trade.profit_pct = profit_pct
        trade.status = 'closed'
        trade.notes += f"\nClosed at: ${exit_price:,.2f}, P&L: ${profit:.2f} ({profit_pct:.2f}%)"
        
        await db_session.commit()
        
        # Send Telegram notification
        await self.notifier.send_trade_exit({
            'symbol': trade.symbol,
            'side': trade.side,
            'entry_price': trade.entry_price,
            'exit_price': exit_price,
            'profit': profit,
            'profit_pct': profit_pct,
            'duration': trade.ts_close,
            'order_id': closure_order['order_id']
        })
        
        return {
            'trade_id': trade_id,
            'exit_price': exit_price,
            'profit': profit,
            'profit_pct': profit_pct,
            'order_id': closure_order['order_id'],
            'status': 'closed'
        }
    
    async def close(self):
        """Close all connections."""
        await self.exchange_manager.close()
    
    async def run_periodic_reconciliation(
        self,
        user_id: str = "default_user",
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Run periodic reconciliation outside of trading cycles.
        
        Should be called every 60 seconds by background task.
        """
        if not db_session:
            return {'status': 'skipped', 'reason': 'No DB session'}
        
        try:
            result = await self.reconciliation_agent.run({
                'user_id': user_id,
                'db_session': db_session
            })
            
            if not result.get('is_synced', True):
                logger.warning(
                    f"⚠️ Reconciliation found issues: "
                    f"{result.get('repaired_count', 0)} repaired, "
                    f"{result.get('orphaned_positions', 0)} orphaned"
                )
                
                # Send alert if critical issues found
                if result.get('ghost_positions', 0) > 0:
                    await self.notifier.send_message(
                        f"🚨 Ghost positions detected: {result['ghost_positions']}"
                    )
            
            return result
            
        except Exception as e:
            logger.error(f"Periodic reconciliation failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def get_system_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive system health report including anomaly detection stats.
        
        Returns:
            Dictionary with system health metrics
        """
        return await self.self_healing_engine.get_health_report()
    
    async def execute_dual_gold_trade(
        self,
        proposal: Dict[str, Any],
        user_id: str = "default_user",
        db_session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Execute Gold trade on MEXC Demo Futures (primary) with optional Binance Testnet comparison.
        
        This implements the hybrid trading strategy for Gold futures comparison.
        Primary execution is now on MEXC Demo Futures for XAUT/USDT.
        
        Args:
            proposal: Trade proposal from AI orchestrator
            user_id: User identifier
            db_session: Database session for persistence
            
        Returns:
            Dictionary with execution results from both exchanges
        """
        # Initialize hybrid manager
        hybrid_manager = HybridExchangeManager()
        
        try:
            # Extract trade parameters
            side = proposal['side'].lower()
            leverage = proposal.get('leverage', 1)
            
            # Calculate quantities for each exchange based on position size
            entry_price = proposal['entry_price']
            quantity = proposal['quantity']
            position_value_usd = entry_price * quantity
            
            # Apply risk management for live MEXC trades using TradeValidator
            validation = await self.validator.validate_trade(
                proposal=proposal,
                user_id=user_id,
                db_session=db_session,
                exchange="mexc",
                symbol=settings.GOLD_SYMBOL_MEXC
            )
            
            # Send validation report to Telegram
            await self.notifier.send_trade_validation_report(validation, proposal)
            
            if not validation.approved:
                error_msg = f"Gold trade REJECTED: {'; '.join(validation.violations)}"
                logger.error(f" {error_msg}")
                raise ValueError(error_msg)
            
            if validation.warnings:
                logger.warning(f"Gold trade approved with warnings: {validation.warnings}")
            
            logger.info(f"\n🥇 Executing dual Gold trade:")
            logger.info(f"   Side: {side.upper()}")
            logger.info(f"   MEXC (Primary/Demo): {settings.GOLD_SYMBOL_MEXC}")
            logger.info(f"   Binance (Comparison/Paper): {settings.GOLD_SYMBOL_BINANCE}")
            logger.info(f"   Position Value: ${position_value_usd:.2f}")
            logger.info(f"   Leverage: {leverage}x")
            
            # Execute on both exchanges simultaneously
            result = await hybrid_manager.execute_dual_trade(
                side=side,
                amount_binance=quantity,
                amount_mexc=quantity,
                leverage=leverage
            )
            
            # Record trades to database
            binance_trade_id = None
            mexc_trade_id = None
            
            if db_session:
                # Record MEXC demo trade (primary)
                if result['mexc'] and result['mexc']['status'] == 'success':
                    mexc_order = result['mexc']['order']
                    mexc_trade = PaperTrades(
                        ts_open=datetime.utcnow().isoformat(),
                        user_id=user_id,
                        exchange='mexc',
                        symbol=settings.GOLD_SYMBOL_MEXC,
                        side=side.upper(),
                        leverage=leverage,
                        qty=quantity,
                        entry_price=mexc_order.get('price') or entry_price,
                        exit_price=None,
                        stop_loss=proposal.get('stop_loss'),
                        take_profit=proposal.get('take_profit'),
                        profit=None,
                        profit_pct=None,
                        status='open',
                        notes=json.dumps({
                            'strategy': proposal.get('strategy_name'),
                            'regime': proposal.get('regime'),
                            'execution_type': 'demo_futures',
                            'order_id': mexc_order.get('order_id'),
                            'paired_with': None  # Will be updated below
                        }),
                        execution_mode='demo'
                    )
                    db_session.add(mexc_trade)
                    await db_session.flush()
                    mexc_trade_id = mexc_trade.id
                
                # Record Binance paper trade (comparison)
                if result['binance'] and result['binance']['status'] == 'success':
                    binance_order = result['binance']['order']
                    binance_trade = PaperTrades(
                        ts_open=datetime.utcnow().isoformat(),
                        user_id=user_id,
                        exchange='binance',
                        symbol=settings.GOLD_SYMBOL_BINANCE,
                        side=side.upper(),
                        leverage=leverage,
                        qty=quantity,
                        entry_price=binance_order.get('price') or entry_price,
                        exit_price=None,
                        stop_loss=proposal.get('stop_loss'),
                        take_profit=proposal.get('take_profit'),
                        profit=None,
                        profit_pct=None,
                        status='open',
                        notes=json.dumps({
                            'strategy': proposal.get('strategy_name'),
                            'regime': proposal.get('regime'),
                            'execution_type': 'paper_testnet',
                            'order_id': binance_order.get('order_id'),
                            'paired_with': mexc_trade_id
                        }),
                        execution_mode='paper'
                    )
                    db_session.add(binance_trade)
                    await db_session.flush()
                    binance_trade_id = binance_trade.id
                
                # Update pairing references
                if binance_trade_id and mexc_trade_id:
                    stmt = select(PaperTrades).where(PaperTrades.id == mexc_trade_id)
                    res = await db_session.execute(stmt)
                    mt = res.scalar_one_or_none()
                    if mt:
                        mt_notes = json.loads(mt.notes) if mt.notes else {}
                        mt_notes['paired_with'] = binance_trade_id
                        mt.notes = json.dumps(mt_notes)
                        await db_session.flush()
            
            # Send Telegram notification
            notifier = TelegramNotifier()
            await notifier.send_gold_dual_trade_alert({
                'binance': result['binance'],
                'mexc': result['mexc'],
                'comparison': {
                    'position_value_usd': position_value_usd,
                    'price_difference': None,  # Will be calculated after both execute
                    'strategy': proposal.get('strategy_name'),
                    'regime': proposal.get('regime'),
                    'confidence': proposal.get('confidence')
                }
            })
            
            return {
                'status': 'success',
                'binance': result['binance'],
                'mexc': result['mexc'],
                'binance_trade_id': binance_trade_id,
                'mexc_trade_id': mexc_trade_id,
                'position_value_usd': position_value_usd
            }
            
        except Exception as e:
            logger.error(f"❌ Dual Gold trade failed: {e}")
            raise
        finally:
            await hybrid_manager.close()
