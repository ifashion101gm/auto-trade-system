"""
Live Trading Service integrating AI decisions with real exchange execution.
Implements complete cycle: Market Data → AI Analysis → Order Execution → Learning
"""
import asyncio
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.ai.orchestrator import AIAgentOrchestrator
from app.infra.exchange_manager import UnifiedExchangeManager
from app.infra.telegram_notifier import TelegramNotifier
from app.storage.models import PaperTrades, DecisionJournal, StrategyEvaluations, TradeProposals
from app.learning.param_cache import LearningParameterCache


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
        self.param_cache = LearningParameterCache()
        
        print(f"✅ Live Trading Service initialized")
        print(f"   Exchange: {self.exchange_name.upper()} ({'TESTNET' if self.use_testnet else 'LIVE'})")
        print(f"   Mode: {self.execution_mode}")
        print(f"   AI: {'OpenRouter' if use_openrouter else 'Heuristic'}")
    
    async def execute_trading_cycle(
        self,
        symbol: str = "BTC/USDT",
        user_id: str = "default_user",
        db_session: Optional[AsyncSession] = None
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
            # Stage 1: Fetch Real Market Data
            print(f"\n📊 Stage 1: Fetching market data for {symbol}...")
            market_data = await self._fetch_market_data(symbol)
            results['stages']['market_data'] = 'success'
            results['market_data'] = market_data
            print(f"   ✅ Current price: ${market_data['current_price']:,.2f}")
            
            # Stage 2: AI Analysis with OpenRouter
            print(f"\n🧠 Stage 2: Running AI analysis...")
            ai_result = await self.orchestrator.run_paper_trade_cycle(
                market_data=market_data,
                user_id=user_id,
                db_session=db_session
            )
            
            if ai_result['status'] != 'success':
                raise Exception(f"AI analysis failed: {ai_result.get('error')}")
            
            results['stages']['ai_analysis'] = 'success'
            results['ai_result'] = ai_result
            print(f"   ✅ Regime: {ai_result['regime']}")
            print(f"   ✅ Strategy: {ai_result['strategy']['strategy']} (confidence: {ai_result['strategy']['confidence']})")
            print(f"   ✅ Risk: {ai_result['risk']['risk_level']}")
            
            # Stage 3: Generate Trade Proposal
            proposal = ai_result['trade_proposal']
            print(f"\n📋 Stage 3: Trade proposal generated")
            print(f"   Side: {proposal['side']}")
            print(f"   Entry: ${proposal['entry_price']:,.2f}")
            print(f"   Stop Loss: ${proposal['stop_loss']:,.2f}")
            print(f"   Take Profit: ${proposal['take_profit']:,.2f}")
            print(f"   Leverage: {proposal['leverage']}x")
            
            # Stage 4: Execute Order (based on execution mode)
            print(f"\n⚡ Stage 4: Executing order (mode: {self.execution_mode})...")
            execution_result = await self._execute_trade(
                proposal=proposal,
                user_id=user_id,
                db_session=db_session
            )
            
            results['stages']['execution'] = execution_result['status']
            results['execution'] = execution_result
            
            if execution_result['status'] == 'executed':
                print(f"   ✅ Order executed: {execution_result.get('order_id')}")
                print(f"   ✅ Filled at: ${execution_result.get('filled_price', 0):,.2f}")
                
                # Stage 5: Send Telegram Notification
                print(f"\n📱 Stage 5: Sending Telegram notification...")
                await self.notifier.send_trade_entry(execution_result)
                results['stages']['notification'] = 'sent'
                
                # Stage 6: Self-Learning Analysis
                print(f"\n🎓 Stage 6: Analyzing for self-learning...")
                learning_result = await self._analyze_and_learn(
                    execution_result=execution_result,
                    ai_result=ai_result,
                    db_session=db_session
                )
                results['stages']['learning'] = 'completed'
                results['learning'] = learning_result
            
            results['status'] = 'success'
            results['cycle_time_ms'] = (time.time() - cycle_start) * 1000
            
            print(f"\n✅ Trading cycle completed in {results['cycle_time_ms']:.0f}ms")
            return results
            
        except Exception as e:
            results['status'] = 'failed'
            results['error'] = str(e)
            results['cycle_time_ms'] = (time.time() - cycle_start) * 1000
            
            print(f"\n❌ Trading cycle failed: {e}")
            import traceback
            traceback.print_exc()
            
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
            # Always require manual execution
            return {
                'status': 'proposal_only',
                'proposal_id': proposal_id,
                'message': 'Trade proposal generated. Manual execution required.',
                'position_value_usd': position_value_usd,
                **proposal
            }
        
        elif self.execution_mode == 'semi-auto':
            # HYBRID MODE: Check position size threshold
            AUTO_EXECUTE_THRESHOLD_USD = settings.AUTO_EXECUTE_THRESHOLD_USD
            
            if position_value_usd <= AUTO_EXECUTE_THRESHOLD_USD:
                # Small position: Auto-execute (fully-auto behavior)
                should_auto_execute = True
                print(f"   💰 Position value: ${position_value_usd:.2f} ≤ ${AUTO_EXECUTE_THRESHOLD_USD:.2f}")
                print(f"   ⚡ Auto-executing (small position)")
            else:
                # Large position: Require confirmation (semi-auto behavior)
                should_auto_execute = False
                print(f"   💰 Position value: ${position_value_usd:.2f} > ${AUTO_EXECUTE_THRESHOLD_USD:.2f}")
                print(f"   ⏸️  Awaiting confirmation (large position)")
                
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
            # Always auto-execute
            should_auto_execute = True
        
        else:
            raise ValueError(f"Invalid execution mode: {self.execution_mode}")
        
        # Execute order if auto-execution is enabled
        if should_auto_execute:
            try:
                # Place market order
                order_result = await self.exchange_manager.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    leverage=leverage
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
        
        print(f"   📊 Slippage: {slippage_pct:.4f}%")
        print(f"   📊 Execution Quality: {learning_insights['execution_quality']}")
        if recommendations:
            print(f"   💡 Recommendations:")
            for rec in recommendations:
                print(f"      - {rec}")
        
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
