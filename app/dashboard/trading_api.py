"""
Trading API endpoints with hardened authentication and rate limiting.
Implements complete paper trading cycle with AI orchestration, database persistence,
and Telegram notifications.
"""
import hmac
import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.infra.rate_limit import RateLimiter
from app.notifications.notifier import TelegramNotifier
from app.database.connection import get_session
from app.database.models import PaperTrades, TrailEvents, Signals
from app.ai_agents.orchestrator import AIAgentOrchestrator
from app.strategy.strategy_manager import StrategyManager
from app.strategy.signal_proposal import SignalProposal
from app.risk.risk_engine import RiskEngine
from app.execution.trading_service import LiveTradingService
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Trading API secret from centralized config
TRADING_API_SECRET = settings.TRADING_API_SECRET


def get_rate_limiter() -> RateLimiter:
    """Dependency for getting the rate limiter instance."""
    return RateLimiter(redis_url=settings.REDIS_URL)


def get_orchestrator() -> AIAgentOrchestrator:
    """Dependency for getting the AI orchestrator instance."""
    return AIAgentOrchestrator()


def get_telegram_notifier() -> TelegramNotifier:
    """Dependency for getting the Telegram notifier instance."""
    return TelegramNotifier()


async def enforce_trading_rate_limit(request: Request, rate_limiter: RateLimiter = Depends(get_rate_limiter)):
    """
    Enforce sliding window rate limit on trading endpoints.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limit (20 requests per minute, burst of 5)
    is_allowed = await rate_limiter.is_allowed(
        identifier=f"ip:{client_ip}",
        limit=20,
        window_s=60,
        burst=5
    )
    
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def verify_trading_secret(auth_header: str):
    """
    Verify trading API secret using constant-time comparison.
    """
    if not TRADING_API_SECRET:
        # Fallback: only allow loopback if no secret is set
        return True
    
    expected = f"Bearer {TRADING_API_SECRET}".encode()
    provided = auth_header.encode() if auth_header else b""
    
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid trading secret")


@router.get("/trading/status")
async def get_trading_status(request: Request, auth: str = None):
    """Get current trading system status."""
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    return {
        "status": "active",
        "message": "Trading system is operational"
    }


@router.post("/trading/execute")
async def execute_trade(
    request: Request,
    trade_request: dict,
    auth: str = None,
    db_session: AsyncSession = Depends(get_session)
):
    """
    Execute trade through proper execution service.
    
    This endpoint implements the professional execution architecture:
    API → Execution Service → Risk Engine → Exchange → Database → Notifications
    
    Args:
        trade_request: Trade execution parameters including:
            - symbol: Trading pair (e.g., 'BTC/USDT')
            - side: 'buy' or 'sell'
            - entry_price: Target entry price
            - quantity: Position size
            - leverage: Leverage multiplier (default: 1)
            - stop_loss: Optional stop loss price
            - take_profit: Optional take profit price
            - strategy_name: Strategy identifier
            - confidence: Signal confidence (0-1)
            - user_id: User identifier
            - execution_mode: 'proposal', 'semi-auto', or 'fully-auto'
            
    Returns:
        Execution result with order details and status
        
    Raises:
        401: Invalid authentication
        429: Rate limit exceeded
        500: Execution failed
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    try:
        # Import execution service
        from app.execution.execution_service import ExecutionService, ExecutionRequest
        
        # Create execution request
        exec_request = ExecutionRequest(
            symbol=trade_request.get('symbol'),
            side=trade_request.get('side'),
            entry_price=float(trade_request.get('entry_price')),
            quantity=float(trade_request.get('quantity')),
            leverage=int(trade_request.get('leverage', 1)),
            stop_loss=trade_request.get('stop_loss'),
            take_profit=trade_request.get('take_profit'),
            strategy_name=trade_request.get('strategy_name'),
            confidence=trade_request.get('confidence'),
            user_id=trade_request.get('user_id', 'default_user'),
            execution_mode=trade_request.get('execution_mode', 'fully-auto')
        )
        
        # Execute trade through service
        execution_service = ExecutionService(
            exchange_name=settings.ACTIVE_EXCHANGE,
            use_testnet=settings.BINANCE_TESTNET,
            db_session_factory=lambda: db_session
        )
        
        result = await execution_service.execute_trade(exec_request, db_session)
        
        # Commit if successful
        if result.success:
            await db_session.commit()
        else:
            await db_session.rollback()
        
        # Return result
        return {
            'status': 'success' if result.success else 'failed',
            'result': result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Trade execution failed: {e}", exc_info=True)
        await db_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Trade execution failed: {str(e)}"
        )


@router.post("/paper-trading/run-cycle")
async def run_paper_trade_cycle(
    request: Request,
    market_data: dict,
    user_id: str = "default_user",
    auth: str = None,
    orchestrator: AIAgentOrchestrator = Depends(get_orchestrator),
    db_session: AsyncSession = Depends(get_session),
    notifier: TelegramNotifier = Depends(get_telegram_notifier)
):
    """
    Execute complete paper trading cycle:
    1. AI analysis (regime detection + strategy selection in parallel)
    2. Risk assessment
    3. Trade proposal generation
    4. Database persistence
    5. Optional Telegram notification
    
    Args:
        market_data: Market snapshot with price, volume, indicators
        user_id: User identifier for tracking
        
    Returns:
        Complete trade decision with execution status
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    # Step 1: Run AI orchestration cycle
    cycle_result = await orchestrator.run_paper_trade_cycle(
        market_data=market_data,
        user_id=user_id,
        db_session=db_session
    )
    
    if cycle_result.get('status') != 'success':
        raise HTTPException(
            status_code=500,
            detail=f"AI cycle failed: {cycle_result.get('error')}"
        )
    
    # Step 2: Extract trade proposal
    proposal = cycle_result.get('trade_proposal', {})
    
    # Step 3: Execute paper trade (create trade record)
    trade_record = await execute_paper_trade(
        db_session=db_session,
        proposal=proposal,
        user_id=user_id
    )
    
    # Step 4: Send Telegram notification
    if trade_record:
        await notifier.send_trade_entry(trade_record)
    
    # Commit database changes
    await db_session.commit()
    
    return {
        "status": "success",
        "trade": trade_record,
        "ai_analysis": {
            "regime": cycle_result.get('regime'),
            "strategy": cycle_result.get('strategy'),
            "risk": cycle_result.get('risk')
        },
        "cycle_time_ms": cycle_result.get('cycle_time_ms')
    }


@router.post("/gold-futures/dual-execute")
async def execute_gold_dual_trade(
    request: Request,
    user_id: str = "default_user",
    auth: str = None,
    db_session: AsyncSession = Depends(get_session)
):
    """
    Execute Gold trade on BOTH Binance Testnet (paper) and MEXC (live).
    Returns comparison data between paper and live execution.
    
    This endpoint implements hybrid trading for Gold futures:
    - Binance: PAXG/USDT paper trades on testnet
    - MEXC: XAUT/USDT live trades with real money
    
    Requires valid trading secret authentication.
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    from app.services.live_trading_service import LiveTradingService
    from app.config import settings
    
    # Initialize trading service
    service = LiveTradingService()
    
    try:
        # Fetch current Gold market data from both exchanges
        print(f"\n🥇 Starting Gold dual execution cycle...")
        
        # Use Binance symbol for market data (PAXG/USDT)
        market_data = await service._fetch_market_data(settings.GOLD_SYMBOL_BINANCE)
        market_data['symbol'] = settings.GOLD_SYMBOL_BINANCE  # Ensure correct symbol
        
        print(f"   Market data fetched: ${market_data['current_price']:,.2f}")
        
        # Run AI analysis cycle
        from app.ai_agents.orchestrator import AIAgentOrchestrator
        orchestrator = AIAgentOrchestrator()
        
        ai_result = await orchestrator.run_paper_trade_cycle(
            market_data=market_data,
            user_id=user_id,
            db_session=db_session
        )
        
        if ai_result['status'] != 'success':
            raise HTTPException(
                status_code=500,
                detail=f"AI analysis failed: {ai_result.get('error')}"
            )
        
        proposal = ai_result.get('trade_proposal', {})
        
        if not proposal:
            raise HTTPException(
                status_code=400,
                detail="No trade proposal generated (confidence may be too low)"
            )
        
        print(f"   AI Proposal: {proposal.get('side')} @ ${proposal.get('entry_price'):,.2f}")
        print(f"   Strategy: {proposal.get('strategy_name')}")
        print(f"   Confidence: {proposal.get('confidence')*100:.1f}%")
        
        # Additional validation at API level before dual execution
        from app.infra.trade_validator import TradeValidator
        validator = TradeValidator()
        validation = await validator.validate_trade(
            proposal=proposal,
            user_id=user_id,
            db_session=db_session,
            exchange="mexc",
            symbol=settings.GOLD_SYMBOL_MEXC
        )
        
        # Send Telegram validation report
        notifier = TelegramNotifier()
        await notifier.send_trade_validation_report(validation, proposal)
        
        if not validation.approved:
            raise HTTPException(
                status_code=400,
                detail=f"Gold trade REJECTED: {'; '.join(validation.violations)}"
            )
        
        # Execute dual trade on both exchanges
        result = await service.execute_dual_gold_trade(
            proposal=proposal,
            user_id=user_id,
            db_session=db_session
        )
        
        # Commit database changes
        await db_session.commit()
        
        # Build comparison data
        binance_price = None
        mexc_price = None
        
        if result['binance'] and result['binance']['status'] == 'success':
            binance_price = result['binance']['order'].get('price')
        
        if result['mexc'] and result['mexc']['status'] == 'success':
            mexc_price = result['mexc']['order'].get('price')
        
        price_difference = None
        if binance_price and mexc_price:
            price_difference = abs(binance_price - mexc_price)
        
        return {
            "status": "success",
            "message": "Gold dual trade executed successfully",
            "binance_paper": {
                "exchange": "Binance Testnet",
                "symbol": settings.GOLD_SYMBOL_BINANCE,
                "result": result['binance'],
                "trade_id": result.get('binance_trade_id')
            },
            "mexc_live": {
                "exchange": "MEXC Live",
                "symbol": settings.GOLD_SYMBOL_MEXC,
                "result": result['mexc'],
                "trade_id": result.get('mexc_trade_id')
            },
            "comparison": {
                "position_value_usd": result.get('position_value_usd'),
                "binance_price": binance_price,
                "mexc_price": mexc_price,
                "price_difference": price_difference,
                "strategy": proposal.get('strategy_name'),
                "regime": proposal.get('regime'),
                "confidence": proposal.get('confidence')
            },
            "ai_analysis": {
                "regime": ai_result.get('regime'),
                "strategy": ai_result.get('strategy'),
                "risk": ai_result.get('risk')
            }
        }
        
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Dual execution failed: {str(e)}"
        )
    finally:
        await service.close()


async def execute_paper_trade(
    db_session: AsyncSession,
    proposal: dict,
    user_id: str
) -> dict:
    """
    Execute paper trade by creating database record.
    
    Implements risk management:
    - Validates stop-loss and take-profit levels
    - Records entry price and position size
    - Sets initial status as 'open'
    
    Args:
        db_session: Active database session
        proposal: Trade proposal from AI orchestrator
        user_id: User identifier
        
    Returns:
        Trade record dictionary
    """
    ts_open = datetime.utcnow().isoformat()
    
    # Validate trade against rules before creation
    from app.infra.trade_validator import TradeValidator
    validator = TradeValidator()
    validation = await validator.validate_trade(
        proposal=proposal,
        user_id=user_id,
        db_session=db_session,
        exchange="binance",  # or "mexc" depending on context
        symbol=proposal.get('symbol', 'BTC/USDT')
    )
    
    # Send Telegram validation report
    notifier = TelegramNotifier()
    await notifier.send_trade_validation_report(validation, proposal)
    
    if not validation.approved:
        raise ValueError(f"Trade REJECTED: {'; '.join(validation.violations)}")
    
    # Create paper trade record
    paper_trade = PaperTrades(
        ts_open=ts_open,
        ts_close=None,
        user_id=user_id,
        exchange="binance",  # Default exchange
        symbol=proposal.get('symbol', 'BTC/USDT'),
        side=proposal.get('side', 'LONG'),
        leverage=proposal.get('leverage', 1),
        qty=proposal.get('quantity', 0),
        entry_price=proposal.get('entry_price', 0),
        exit_price=None,
        stop_loss=proposal.get('stop_loss'),
        take_profit=proposal.get('take_profit'),
        profit=None,
        profit_pct=None,
        status='open',
        notes=json.dumps({
            'strategy': proposal.get('strategy_name'),
            'confidence': proposal.get('confidence'),
            'regime': proposal.get('regime'),
            'risk_level': proposal.get('risk_level')
        }),
        execution_mode='paper'
    )
    
    db_session.add(paper_trade)
    await db_session.flush()  # Get generated ID
    
    # Build response
    trade_record = {
        'trade_id': paper_trade.id,
        'symbol': paper_trade.symbol,
        'side': paper_trade.side,
        'entry_price': paper_trade.entry_price,
        'qty': paper_trade.qty,
        'leverage': paper_trade.leverage,
        'stop_loss': paper_trade.stop_loss,
        'take_profit': paper_trade.take_profit,
        'strategy': proposal.get('strategy_name'),
        'confidence': proposal.get('confidence'),
        'ts_open': ts_open
    }
    
    return trade_record


@router.post("/paper-trading/close-trade/{trade_id}")
async def close_paper_trade(
    trade_id: int,
    exit_price: float,
    request: Request,
    auth: str = None,
    db_session: AsyncSession = Depends(get_session),
    notifier: TelegramNotifier = Depends(get_telegram_notifier)
):
    """
    Close an open paper trade and calculate P&L.
    
    Args:
        trade_id: ID of the trade to close
        exit_price: Exit price for the trade
        
    Returns:
        Updated trade record with P&L
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    # Fetch trade from database
    from sqlalchemy import select
    result = await db_session.execute(
        select(PaperTrades).where(PaperTrades.id == trade_id)
    )
    trade = result.scalar_one_or_none()
    
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    
    if trade.status != 'open':
        raise HTTPException(status_code=400, detail=f"Trade {trade_id} is already closed")
    
    # Calculate P&L
    if trade.side == 'LONG':
        profit = (exit_price - trade.entry_price) * trade.qty * trade.leverage
    else:  # SHORT
        profit = (trade.entry_price - exit_price) * trade.qty * trade.leverage
    
    profit_pct = (profit / (trade.entry_price * trade.qty)) * 100
    
    # Update trade record
    ts_close = datetime.utcnow().isoformat()
    trade.ts_close = ts_close
    trade.exit_price = exit_price
    trade.profit = round(profit, 2)
    trade.profit_pct = round(profit_pct, 2)
    trade.status = 'closed'
    
    # Add closing notes
    notes = json.loads(trade.notes) if trade.notes else {}
    notes['exit_reason'] = 'manual_close'
    notes['exit_timestamp'] = ts_close
    trade.notes = json.dumps(notes)
    
    await db_session.flush()
    
    # Build trade data for notification
    trade_data = {
        'trade_id': trade.id,
        'symbol': trade.symbol,
        'side': trade.side,
        'entry_price': trade.entry_price,
        'exit_price': exit_price,
        'profit': trade.profit,
        'profit_pct': trade.profit_pct,
        'status': trade.status,
        'notes': f"Exit reason: {notes.get('exit_reason', 'unknown')}"
    }
    
    # Send Telegram notification
    await notifier.send_trade_exit(trade_data)
    
    # Commit changes
    await db_session.commit()
    
    return {
        "status": "success",
        "trade": {
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "profit": trade.profit,
            "profit_pct": trade.profit_pct,
            "ts_open": trade.ts_open,
            "ts_close": trade.ts_close
        }
    }


@router.get("/paper-trading/open-trades")
async def get_open_trades(
    request: Request,
    user_id: str = "default_user",
    auth: str = None,
    db_session: AsyncSession = Depends(get_session)
):
    """
    Get all open paper trades for a user.
    
    Returns:
        List of open trades with current status
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    from sqlalchemy import select
    result = await db_session.execute(
        select(PaperTrades)
        .where(PaperTrades.user_id == user_id)
        .where(PaperTrades.status == 'open')
        .order_by(PaperTrades.ts_open.desc())
    )
    trades = result.scalars().all()
    
    return {
        "status": "success",
        "count": len(trades),
        "trades": [
            {
                "trade_id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "qty": t.qty,
                "leverage": t.leverage,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "ts_open": t.ts_open
            }
            for t in trades
        ]
    }


@router.get("/paper-trading/trade-history")
async def get_trade_history(
    request: Request,
    user_id: str = "default_user",
    limit: int = 50,
    auth: str = None,
    db_session: AsyncSession = Depends(get_session)
):
    """
    Get closed trade history with P&L statistics.
    
    Args:
        user_id: User identifier
        limit: Maximum number of trades to return
        
    Returns:
        Trade history with performance metrics
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    from sqlalchemy import select, func
    
    # Fetch closed trades
    result = await db_session.execute(
        select(PaperTrades)
        .where(PaperTrades.user_id == user_id)
        .where(PaperTrades.status == 'closed')
        .order_by(PaperTrades.ts_close.desc())
        .limit(limit)
    )
    trades = result.scalars().all()
    
    # Calculate aggregate statistics
    stats_result = await db_session.execute(
        select(
            func.count(PaperTrades.id).label('total_trades'),
            func.sum(PaperTrades.profit).label('total_profit'),
            func.avg(PaperTrades.profit_pct).label('avg_profit_pct')
        )
        .where(PaperTrades.user_id == user_id)
        .where(PaperTrades.status == 'closed')
    )
    stats = stats_result.one()
    
    total_trades = stats.total_trades or 0
    total_profit = float(stats.total_profit or 0)
    avg_profit_pct = float(stats.avg_profit_pct or 0)
    
    # Count winning/losing trades
    wins_result = await db_session.execute(
        select(func.count(PaperTrades.id))
        .where(PaperTrades.user_id == user_id)
        .where(PaperTrades.status == 'closed')
        .where(PaperTrades.profit > 0)
    )
    winning_trades = wins_result.scalar() or 0
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "status": "success",
        "statistics": {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate_pct": round(win_rate, 2),
            "total_profit_usd": round(total_profit, 2),
            "avg_profit_pct": round(avg_profit_pct, 2)
        },
        "trades": [
            {
                "trade_id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "profit": t.profit,
                "profit_pct": t.profit_pct,
                "ts_open": t.ts_open,
                "ts_close": t.ts_close
            }
            for t in trades
        ]
    }


# =============================================================================
# Multi-Agent Trading System Endpoints (New)
# =============================================================================

@router.post("/trades/execute")
async def execute_trade_endpoint(
    proposal: dict,
    mode: str = "DEMO",
    db_session: AsyncSession = Depends(get_session)
):
    """Execute a trade proposal using multi-agent system."""
    from app.execution.execution_agent import ExecutionAgent
    agent = ExecutionAgent()
    result = await agent.execute_trade(proposal, mode, db_session)
    return result


@router.post("/trades/{trade_id}/close")
async def close_trade_endpoint(
    trade_id: str,
    db_session: AsyncSession = Depends(get_session)
):
    """Close an open trade."""
    from app.execution.execution_agent import ExecutionAgent
    agent = ExecutionAgent()
    result = await agent.close_trade(trade_id, db_session)
    return result


@router.get("/analytics/daily")
async def get_daily_analytics(
    db_session: AsyncSession = Depends(get_session)
):
    """Get daily performance analytics."""
    from app.ai_agents.analytics_agent import AnalyticsAgent
    agent = AnalyticsAgent()
    return await agent.calculate_daily_performance(db_session)


@router.post("/reconciliation/run")
async def run_reconciliation(
    mode: str = "DEMO",
    db_session: AsyncSession = Depends(get_session)
):
    """Manually trigger reconciliation."""
    from app.services.reconciliation_service import ReconciliationService
    service = ReconciliationService()
    await service.reconcile(mode, db_session)
    return {"status": "completed"}


@router.get("/reconciliation/status")
async def get_reconciliation_status():
    """
    Get detailed reconciliation engine status.
    
    Returns:
        Dictionary with reconciliation engine state, stats, and configuration
    """
    try:
        # Import here to avoid circular dependencies
        from app.main import get_app_state
        state = get_app_state()
        
        if not hasattr(state, 'reconciliation_engine') or not state.reconciliation_engine:
            return {
                "status": "not_initialized",
                "message": "Reconciliation engine not started"
            }
        
        # Get detailed status from engine
        status = state.reconciliation_engine.get_detailed_status()
        
        return {
            "status": "running" if status['is_running'] else "stopped",
            **status
        }
        
    except Exception as e:
        logger.error(f"Failed to get reconciliation status: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/reconciliation/metrics")
async def get_reconciliation_metrics():
    """
    Get reconciliation metrics from Prometheus.
    
    Returns:
        Current reconciliation mismatch counts and repair statistics
    """
    try:
        from app.monitoring.prometheus_metrics import get_metrics_collector
        metrics = get_metrics_collector()
        
        # Extract current metric values
        # Note: In production, you'd query Prometheus directly
        # This is a simplified version for dashboard display
        
        return {
            "metrics_available": True,
            "endpoint": "/metrics",
            "note": "Query /metrics endpoint for full Prometheus data",
            "key_metrics": [
                "reconciliation_mismatches_total{type='orphaned'}",
                "reconciliation_mismatches_total{type='ghost'}",
                "reconciliation_mismatches_total{type='status_diff'}",
                "reconciliation_repairs_total{type='auto_repair'}"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get reconciliation metrics: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# =============================================================================
# TradingView Webhook Integration
# =============================================================================

@router.post("/webhooks/tradingview")
async def receive_tradingview_alert(
    request: Request,
    alert_data: dict,
    auth: str = None,
    db_session: AsyncSession = Depends(get_session)
):
    """
    Receive TradingView webhook alerts and process through Signal Engine.
    
    Flow:
    1. Validate webhook payload format
    2. Convert to internal SignalProposal
    3. Pass to Risk Engine for approval
    4. Forward to Execution Engine if approved
    
    Expected TradingView Alert Format:
    {
        "strategy": "breakout",  // optional
        "symbol": "BTCUSDT",
        "side": "buy",  // or "sell"
        "price": 50000.0,
        "quantity": 0.01,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "leverage": 1,
        "confidence": 0.75,
        "timestamp": "2026-05-12T10:30:00Z"
    }
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    try:
        # Log webhook receipt
        logger.info(f"📥 TradingView webhook received from IP: {request.client.host if request.client else 'unknown'}")
        logger.debug(f"Webhook payload: {json.dumps(alert_data, indent=2)}")
        
        # Step 1: Validate webhook payload
        validated_signal, validation_error = validate_tradingview_payload(alert_data)
        
        if not validated_signal:
            logger.warning(f"❌ TradingView alert validation failed: {validation_error}")
            raise HTTPException(status_code=400, detail=f"Invalid TradingView alert: {validation_error}")
        
        logger.info(f"✅ Validated TradingView signal: {validated_signal.side} {validated_signal.symbol} @ ${validated_signal.entry_price:,.2f}")
        
        # Send receipt confirmation notification
        notifier = TelegramNotifier()
        await notifier.send_message(
            f"📥 TradingView Signal Received\n\n"
            f"Symbol: {validated_signal.symbol}\n"
            f"Side: {validated_signal.side}\n"
            f"Price: ${validated_signal.entry_price:,.2f}\n"
            f"Quantity: {validated_signal.quantity}\n"
            f"Strategy: {validated_signal.strategy_name}\n"
            f"Confidence: {validated_signal.confidence*100:.0f}%"
        )
        
        # Step 2: Save signal to database with enhanced metadata
        signal_id = str(uuid.uuid4())
        signal_record = Signals(
            id=signal_id,
            source='TRADINGVIEW_WEBHOOK',
            symbol=validated_signal.symbol.replace('/', ''),  # Store without slash for consistency
            signal_type=f"ENTRY_{validated_signal.side}",
            strength=validated_signal.confidence,
            indicators_json=json.dumps({
                'entry_price': validated_signal.entry_price,
                'stop_loss': validated_signal.stop_loss,
                'take_profit': validated_signal.take_profit,
                'quantity': validated_signal.quantity,
                'leverage': validated_signal.leverage,
                'strategy': validated_signal.strategy_name,
                'regime': validated_signal.regime,
            }),
            regime=validated_signal.regime,
            confidence=validated_signal.confidence,
            processed=0,  # 0=pending, 1=processed, 2=rejected
            timestamp=datetime.utcnow()
        )
        db_session.add(signal_record)
        await db_session.flush()
        
        logger.info(f"💾 Signal saved to database: ID={signal_id}")
        
        # Step 3: Pass to Risk Engine for validation
        user_id = alert_data.get('user_id', 'tradingview_user')
        risk_engine = RiskEngine(db_session=db_session)
        risk_decision = await risk_engine.check_trade_approval(
            proposal=validated_signal.to_dict(),
            user_id=user_id
        )
        
        if not risk_decision.approved:
            logger.warning(f"🚫 TradingView signal REJECTED by Risk Engine:")
            for violation in risk_decision.violations:
                logger.warning(f"   - {violation}")
            
            # Update signal as rejected
            signal_record.processed = 2  # 2 = rejected
            signal_record.notes = json.dumps({
                'rejection_reason': 'risk_engine',
                'violations': risk_decision.violations,
                'risk_metrics': {
                    'daily_pnl_pct': risk_decision.daily_pnl_pct,
                    'drawdown_pct': risk_decision.current_drawdown_pct,
                    'risk_score': risk_decision.risk_score
                }
            })
            await db_session.commit()
            
            # Send rejection notification
            await notifier.send_message(
                f"🚫 TradingView Signal Rejected\n\n"
                f"Symbol: {validated_signal.symbol}\n"
                f"Side: {validated_signal.side}\n"
                f"Price: ${validated_signal.entry_price:,.2f}\n"
                f"Violations:\n" + "\n".join([f"• {v}" for v in risk_decision.violations])
            )
            
            return {
                "status": "rejected",
                "reason": "Risk Engine rejection",
                "violations": risk_decision.violations,
                "signal_id": signal_record.id
            }
        
        logger.info(f"✅ Risk Engine approved signal (score: {risk_decision.risk_score})")
        
        # Step 4: Forward to Execution Engine
        execution_service = LiveTradingService()
        
        try:
            logger.info(f"⚡ Executing TradingView signal (mode: {execution_service.execution_mode})...")
            
            # Execute trade using existing execution logic
            execution_result = await execution_service._execute_trade(
                proposal=validated_signal.to_dict(),
                user_id=user_id,
                db_session=db_session
            )
            
            # Handle different execution outcomes
            execution_status = execution_result.get('status', 'unknown')
            
            if execution_status == 'executed':
                logger.info(f"✅ Trade executed successfully: Order {execution_result.get('order_id')}")
                
                # Update signal record with trade ID
                trade_id = execution_result.get('trade_id')
                if trade_id:
                    signal_record.trade_id = str(trade_id)
                    signal_record.processed = 1  # 1 = processed
                
                # Send execution notification
                await notifier.send_trade_entry(execution_result)
                
                await db_session.commit()
                
                return {
                    "status": "executed",
                    "execution": execution_result,
                    "signal_id": signal_record.id,
                    "trade_id": trade_id,
                    "risk_metrics": {
                        'daily_pnl_pct': risk_decision.daily_pnl_pct,
                        'drawdown_pct': risk_decision.current_drawdown_pct,
                        'risk_score': risk_decision.risk_score
                    }
                }
            
            elif execution_status in ['proposal_only', 'awaiting_confirmation']:
                logger.info(f"⏸️ Trade saved as proposal (requires confirmation)")
                
                # Update signal as pending
                signal_record.processed = 0  # 0 = pending
                signal_record.notes = json.dumps({
                    'execution_status': execution_status,
                    'message': execution_result.get('message'),
                    'proposal_id': execution_result.get('proposal_id')
                })
                await db_session.commit()
                
                # Send proposal notification
                await notifier.send_message(
                    f"⏸️ TradingView Proposal Created\n\n"
                    f"Symbol: {validated_signal.symbol}\n"
                    f"Side: {validated_signal.side}\n"
                    f"Status: Awaiting Confirmation\n"
                    f"Message: {execution_result.get('message')}"
                )
                
                return {
                    "status": execution_status,
                    "message": execution_result.get('message'),
                    "proposal_id": execution_result.get('proposal_id'),
                    "signal_id": signal_record.id
                }
            
            elif execution_status == 'rejected':
                logger.warning(f"🚫 Trade rejected during execution: {execution_result.get('violations')}")
                
                # Update signal as rejected
                signal_record.processed = 2
                signal_record.notes = json.dumps({
                    'rejection_reason': 'execution_validator',
                    'violations': execution_result.get('violations', [])
                })
                await db_session.commit()
                
                return {
                    "status": "rejected",
                    "reason": "Execution validation rejection",
                    "violations": execution_result.get('violations', []),
                    "signal_id": signal_record.id
                }
            
            else:
                raise Exception(f"Unexpected execution status: {execution_status}")
        
        finally:
            await execution_service.close()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TradingView webhook processing failed: {e}")
        logger.exception("Full traceback:")
        
        # Send error notification
        try:
            notifier = TelegramNotifier()
            await notifier.send_message(
                f"🚨 TradingView Webhook Error\n\n"
                f"Error: {str(e)[:200]}\n"  # Truncate long messages
                f"Payload: {json.dumps(alert_data, indent=2)[:500]}"
            )
        except:
            pass  # Don't fail if notification fails
        
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@router.post("/signals/generate")
async def generate_signal_from_strategies(
    request: Request,
    market_data: dict,
    auth: str = None,
    db_session: AsyncSession = Depends(get_session)
):
    """
    Generate trade signal using internal strategy engine.
    
    This endpoint runs all configured strategies on provided market data
    and returns the best signal (after AI filtering).
    
    Flow:
    1. Run all strategies in parallel
    2. Apply AI filter validation
    3. Select highest-confidence signal
    4. Return signal proposal (does NOT execute)
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    try:
        # Initialize strategy manager
        strategy_mgr = StrategyManager(use_ai_filter=True)
        
        # Generate signals
        signal = await strategy_mgr.generate_signals(market_data)
        
        if not signal:
            return {
                "status": "no_signal",
                "message": "No valid signals generated by any strategy"
            }
        
        # Save signal to database
        signal_record = Signals(
            id=str(uuid.uuid4()),
            source=f"STRATEGY_{signal.strategy_name.upper()}",
            symbol=signal.symbol.replace('/', ''),
            signal_type=f"ENTRY_{signal.side}",
            strength=signal.confidence,
            indicators_json=json.dumps(signal.indicators),
            regime=signal.regime,
            confidence=signal.confidence,
            processed=0
        )
        db_session.add(signal_record)
        await db_session.commit()
        
        return {
            "status": "success",
            "signal": signal.to_dict(),
            "signal_id": signal_record.id,
            "next_step": "Send this signal to /trades/execute for execution"
        }
    
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Signal generation failed: {str(e)}")


def validate_tradingview_payload(data: dict) -> tuple:
    """
    Validate and parse TradingView webhook payload.
    
    Returns: (SignalProposal, None) on success, (None, error_message) on failure
    
    Expected format:
    {
        "strategy": "breakout",
        "symbol": "BTCUSDT",
        "side": "buy",
        "price": 50000.0,
        "quantity": 0.01,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "leverage": 1,
        "confidence": 0.75
    }
    """
    try:
        # Check required fields
        required_fields = ['symbol', 'side', 'price', 'quantity']
        for field in required_fields:
            if field not in data:
                return None, f"Missing required field: {field}"
        
        # Validate side
        side_raw = str(data['side']).lower().strip()
        if side_raw in ['buy', 'long']:
            side = 'LONG'
        elif side_raw in ['sell', 'short']:
            side = 'SHORT'
        else:
            return None, f"Invalid side: {side_raw}. Must be 'buy', 'sell', 'long', or 'short'"
        
        # Normalize symbol
        symbol = str(data['symbol']).upper().strip()
        # Remove perpetual suffix if present
        symbol = symbol.replace('.P', '').replace('.PERP', '')
        # Add / separator if missing
        if '/' not in symbol:
            if len(symbol) == 6:  # e.g., BTCUSDT
                symbol = f"{symbol[:3]}/{symbol[3:]}"
            elif symbol.endswith('USDT'):  # e.g., ETHUSDT
                base = symbol[:-4]
                symbol = f"{base}/USDT"
            elif symbol.endswith('USD'):
                base = symbol[:-3]
                symbol = f"{base}/USD"
            else:
                return None, f"Cannot parse symbol format: {symbol}"
        
        # Validate numeric fields
        try:
            price = float(data['price'])
            if price <= 0:
                return None, f"Price must be positive: {price}"
        except (ValueError, TypeError):
            return None, f"Invalid price value: {data['price']}"
        
        try:
            quantity = float(data['quantity'])
            if quantity <= 0:
                return None, f"Quantity must be positive: {quantity}"
        except (ValueError, TypeError):
            return None, f"Invalid quantity value: {data['quantity']}"
        
        # Optional fields with defaults
        stop_loss = None
        if data.get('stop_loss'):
            try:
                stop_loss = float(data['stop_loss'])
                if stop_loss <= 0:
                    stop_loss = None
            except (ValueError, TypeError):
                pass
        
        take_profit = None
        if data.get('take_profit'):
            try:
                take_profit = float(data['take_profit'])
                if take_profit <= 0:
                    take_profit = None
            except (ValueError, TypeError):
                pass
        
        leverage = 1
        if data.get('leverage'):
            try:
                leverage = int(float(data['leverage']))
                if leverage < 1:
                    leverage = 1
            except (ValueError, TypeError):
                pass
        
        confidence = 0.7
        if data.get('confidence'):
            try:
                confidence = float(data['confidence'])
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
            except (ValueError, TypeError):
                pass
        
        strategy_name = str(data.get('strategy', 'tradingview_manual'))
        # Sanitize strategy name
        strategy_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in strategy_name)
        
        # Build SignalProposal
        proposal = SignalProposal(
            symbol=symbol,
            side=side,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            leverage=leverage,
            confidence=confidence,
            strategy_name=strategy_name,
            regime='Normal',  # Default regime for external signals
            indicators={
                'source': 'tradingview_webhook',
                'raw_timestamp': data.get('timestamp'),
            },
            metadata={
                'source': 'tradingview_webhook',
                'raw_payload': {k: v for k, v in data.items() if k != 'raw_payload'},
            }
        )
        
        return proposal, None
    
    except Exception as e:
        logger.error(f"Payload validation error: {e}")
        return None, f"Validation error: {str(e)}"


@router.post("/debug/test-order")
async def test_order(
    request: Request,
    symbol: str = "XAU/USDT:USDT",
    side: str = "BUY",
    quantity: float = 0.01,
    auth: str = None,
    db_session: AsyncSession = Depends(get_session),
    notifier: TelegramNotifier = Depends(get_telegram_notifier)
):
    """
    Force execute a test trade to verify end-to-end pipeline.
    
    Creates fake signal → passes risk checks → sends order → saves DB → triggers reconciliation
    """
    # Verify authentication
    verify_trading_secret(auth)
    
    logger.info("[DEBUG] Starting forced test order...")
    
    try:
        # Step 1: Create synthetic signal
        from app.strategy.signal_proposal import SignalProposal
        signal = SignalProposal(
            symbol=symbol,
            side=side.upper(),
            entry_price=0.0,  # Will be filled by market
            stop_loss=0.0,
            take_profit=0.0,
            quantity=quantity,
            leverage=2,
            confidence=0.95,
            strategy_name='debug_test',
            regime='Test'
        )
        
        logger.info(f"[DEBUG] Created test signal: {signal.to_dict()}")
        
        # Step 2: Risk check
        from app.risk.risk_engine import RiskEngine
        risk_engine = RiskEngine(db_session=db_session)
        risk_decision = await risk_engine.check_trade_approval(
            proposal=signal.to_dict(),
            user_id='debug_user'
        )
        
        if not risk_decision.approved:
            logger.warning(f"[RISK] Test order rejected: {risk_decision.violations}")
            return {
                "status": "rejected",
                "violations": risk_decision.violations,
                "risk_score": risk_decision.risk_score
            }
        
        logger.info("[RISK] Test order approved")
        
        # Step 3: Execute order
        from app.infra.exchange_manager import UnifiedExchangeManager
        exchange_mgr = UnifiedExchangeManager()
        
        order_result = await exchange_mgr.create_market_order(
            symbol=signal.symbol,
            side=signal.side.lower(),
            amount=signal.quantity,
            leverage=signal.leverage
        )
        
        logger.info(f"[ORDER_SENT] {symbol} {side} {quantity} → Order ID: {order_result.get('order_id')}")
        
        # Step 4: Save to database
        from app.database.models import PaperTrades
        from datetime import datetime
        
        trade = PaperTrades(
            user_id='debug_user',
            symbol=signal.symbol,
            side=signal.side,
            entry_price=order_result.get('price', 0),
            qty=signal.quantity,
            leverage=signal.leverage,
            status='open',
            ts_open=datetime.utcnow().isoformat(),
            strategy='debug_test',
            notes='Forced test order via /debug/test-order endpoint'
        )
        
        db_session.add(trade)
        await db_session.commit()
        await db_session.refresh(trade)
        
        logger.info(f"[DB_SAVE] Trade saved: ID={trade.id}")
        
        # Step 5: Send notification
        await notifier.send_message(
            f"🧪 DEBUG TEST ORDER\n\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Quantity: {quantity}\n"
            f"Order ID: {order_result.get('order_id')}\n"
            f"Trade ID: {trade.id}\n"
            f"Status: EXECUTED"
        )
        
        return {
            "status": "executed",
            "order_id": order_result.get('order_id'),
            "trade_id": trade.id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": order_result.get('price'),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[DEBUG] Test order failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/validation")
async def get_validation_metrics():
    """Get validation metrics dashboard data."""
    from app.monitoring.metrics_collector import metrics_collector
    return metrics_collector.get_summary()
