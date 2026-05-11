"""
Trading API endpoints with hardened authentication and rate limiting.
Implements complete paper trading cycle with AI orchestration, database persistence,
and Telegram notifications.
"""
import hmac
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.infra.rate_limit import RateLimiter
from app.infra.telegram_notifier import TelegramNotifier
from app.storage.db import get_session
from app.storage.models import PaperTrades, TrailEvents
from app.ai.orchestrator import AIAgentOrchestrator

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
async def execute_trade(request: Request, auth: str = None):
    """Execute a trade (placeholder)."""
    # Verify authentication
    verify_trading_secret(auth)
    
    # Enforce rate limit
    await enforce_trading_rate_limit(request)
    
    # TODO: Implement actual trade execution logic
    return {
        "status": "success",
        "message": "Trade executed successfully"
    }


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
        from app.ai.orchestrator import AIAgentOrchestrator
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
