"""
SQLAlchemy ORM models for the Auto Trade System.
Aligned with migrations/versions/001_initial_schema.py
"""
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Index, DateTime, func
from app.database.connection import Base


class ModelUsage(Base):
    __tablename__ = 'model_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    endpoint = Column(Text, nullable=False)
    task_type = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    latency_ms = Column(Float, nullable=False)
    estimated_cost_usd = Column(Float, nullable=False)

    __table_args__ = (
        Index('idx_model_usage_ts', 'ts'),
        Index('idx_model_usage_model', 'model'),
    )


class AssistantMemory(Base):
    __tablename__ = 'assistant_memory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    __table_args__ = (
        Index('idx_assistant_memory_user_ts', 'user_id', 'ts'),
    )


class DecisionJournal(Base):
    __tablename__ = 'decision_journal'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    prompt = Column(Text, nullable=False)
    reply = Column(Text, nullable=False)
    task_type = Column(Text, nullable=False)

    __table_args__ = (
        Index('idx_decision_journal_user_ts', 'user_id', 'ts'),
    )


class StrategyRegistry(Base):
    __tablename__ = 'strategy_registry'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    strategy_id = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    source = Column(Text, nullable=False)
    description = Column(Text, nullable=False)


class StrategyEvaluations(Base):
    __tablename__ = 'strategy_evaluations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    strategy_id = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    metrics_json = Column(Text, nullable=False)

    __table_args__ = (
        Index('idx_strategy_evaluations_strategy', 'strategy_id'),
    )


class PaperTrades(Base):
    __tablename__ = 'paper_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_open = Column(Text, nullable=False)
    ts_close = Column(Text, nullable=True)
    user_id = Column(Text, nullable=False)
    exchange = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    leverage = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    profit_pct = Column(Float, nullable=True)
    status = Column(Text, nullable=False, server_default='open')
    notes = Column(Text, nullable=True)
    execution_mode = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_paper_trades_user_status', 'user_id', 'status'),
        Index('idx_paper_trades_symbol', 'symbol'),
        Index('idx_paper_trades_ts_open', 'ts_open'),
    )


class TrailEvents(Base):
    __tablename__ = 'trail_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    trade_id = Column(Integer, nullable=False)
    old_stop = Column(Float, nullable=False)
    new_stop = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)

    __table_args__ = (
        Index('idx_trail_events_trade', 'trade_id'),
    )


class TradeProposals(Base):
    __tablename__ = 'trade_proposals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    exchange = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    strategy_name = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default='pending')
    ai_metadata = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_trade_proposals_user_status', 'user_id', 'status'),
    )


class StrategyParameters(Base):
    __tablename__ = 'strategy_parameters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    strategy_name = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    timeframe = Column(Text, nullable=False)
    parameter_set = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, server_default='1')
    is_active = Column(Integer, nullable=False, server_default='0')
    optimization_run_id = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_strategy_parameters_strategy', 'strategy_name'),
    )


class BacktestRuns(Base):
    __tablename__ = 'backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    run_id = Column(Text, nullable=False, unique=True)
    strategy_name = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    timeframe = Column(Text, nullable=False)
    start_date = Column(Text, nullable=False)
    end_date = Column(Text, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float, nullable=True)
    total_return_pct = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    status = Column(Text, nullable=False, server_default='running')
    ai_decision_log = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_backtest_runs_strategy', 'strategy_name'),
    )


class OptimizationRuns(Base):
    __tablename__ = 'optimization_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    run_id = Column(Text, nullable=False, unique=True)
    strategy_name = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    timeframe = Column(Text, nullable=False)
    optimization_method = Column(Text, nullable=False)
    parameter_space = Column(Text, nullable=False)
    objective_metric = Column(Text, nullable=False)
    num_iterations = Column(Integer, nullable=True)
    best_score = Column(Float, nullable=True)
    best_parameters = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default='running')
    completed_at = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_optimization_runs_strategy', 'strategy_name'),
    )


class PerformancePeriods(Base):
    __tablename__ = 'performance_periods'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    period_start = Column(Text, nullable=False)
    period_end = Column(Text, nullable=False)
    strategy_name = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False)
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    losing_trades = Column(Integer, nullable=False)
    win_rate = Column(Float, nullable=False)
    total_profit = Column(Float, nullable=False)
    avg_profit_per_trade = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    expectancy = Column(Float, nullable=True)
    calmar_ratio = Column(Float, nullable=True)
    recovery_factor = Column(Float, nullable=True)
    var_95 = Column(Float, nullable=True)
    cvar_95 = Column(Float, nullable=True)
    beta = Column(Float, nullable=True)
    alpha = Column(Float, nullable=True)
    avg_trade_duration_hours = Column(Float, nullable=True)
    trade_frequency_per_day = Column(Float, nullable=True)
    avg_holding_period_hours = Column(Float, nullable=True)

    __table_args__ = (
        Index('idx_performance_periods_strategy', 'strategy_name'),
    )


class OptimizationResults(Base):
    __tablename__ = 'optimization_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False)
    optimization_run_id = Column(Text, nullable=False)
    rank = Column(Integer, nullable=False)
    parameters = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    metrics_json = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_optimization_results_run', 'optimization_run_id'),
    )


class SchemaMigrations(Base):
    __tablename__ = 'schema_migrations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Text, nullable=False, unique=True)
    applied_at = Column(Text, nullable=False)
    description = Column(Text, nullable=True)


# =============================================================================
# Multi-Agent Trading System Models (New)
# =============================================================================


class Trades(Base):
    """Enhanced trades table for multi-agent system with complete state machine."""
    __tablename__ = 'trades'

    id = Column(String(36), primary_key=True)
    mode = Column(String(10), nullable=False)  # 'LIVE' or 'DEMO'
    exchange = Column(String(20), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'LONG' or 'SHORT'
    status = Column(String(20), nullable=False)  # PENDING, OPEN, PARTIAL, TP_HIT, SL_HIT, CLOSED, ERROR, CANCELLED
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    leverage = Column(Integer, nullable=False)
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, nullable=True)  # Track partial fills
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    exchange_order_id = Column(String(100), nullable=True)
    strategy_name = Column(String(100), nullable=True)
    regime = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)  # Store error details
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=True)
    closed_at = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_trades_status', 'status'),
        Index('idx_trades_symbol', 'symbol'),
        Index('idx_trades_created_at', 'created_at'),
    )


class Positions(Base):
    """Real-time position tracking with sync source."""
    __tablename__ = 'positions'

    id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), nullable=True)
    symbol = Column(String(20), nullable=False)
    size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=True)  # For partial closes
    liquidation_price = Column(Float, nullable=True)
    leverage = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)  # 'open', 'partial', 'closed'
    last_sync = Column(DateTime, nullable=True)
    sync_source = Column(String(20), nullable=True)  # 'websocket', 'rest', 'recovery'

    __table_args__ = (
        Index('idx_positions_status', 'status'),
        Index('idx_positions_symbol', 'symbol'),
    )


class OrderEvents(Base):
    """Event sourcing for order lifecycle."""
    __tablename__ = 'order_events'

    id = Column(String(36), primary_key=True)
    trade_id = Column(String(36), nullable=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(Text, nullable=False)  # JSON string
    created_at = Column(Text, nullable=False)

    __table_args__ = (
        Index('idx_order_events_trade_id', 'trade_id'),
        Index('idx_order_events_type', 'event_type'),
    )


class SyncLogs(Base):
    """Reconciliation tracking logs."""
    __tablename__ = 'sync_logs'

    id = Column(String(36), primary_key=True)
    timestamp = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)  # 'mexc_live', 'mexc_demo'
    event_type = Column(String(50), nullable=False)
    data = Column(Text, nullable=False)  # JSON string
    processed = Column(Integer, nullable=False, server_default='0')

    __table_args__ = (
        Index('idx_sync_logs_timestamp', 'timestamp'),
    )


class TelegramNotifications(Base):
    """Telegram notification history."""
    __tablename__ = 'telegram_notifications'

    id = Column(String(36), primary_key=True)
    timestamp = Column(Text, nullable=False)
    message_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    sent = Column(Integer, nullable=False, server_default='0')
    error = Column(Text, nullable=True)


# =============================================================================
# Order Execution Engine Models (Steps 9-12)
# =============================================================================


class Orders(Base):
    """Individual order lifecycle tracking."""
    __tablename__ = 'orders'

    id = Column(String(36), primary_key=True)  # UUID
    client_order_id = Column(String(100), nullable=False, unique=True, index=True)  # Idempotency key
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=True, index=True)
    exchange = Column(String(20), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'BUY' or 'SELL'
    order_type = Column(String(20), nullable=False)  # 'MARKET', 'LIMIT', 'STOP_LOSS'
    status = Column(String(30), nullable=False, index=True)  # Maps to OrderState values
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, nullable=False, server_default='0')
    remaining_quantity = Column(Float, nullable=False, server_default='0')
    price = Column(Float, nullable=True)  # For limit orders
    average_fill_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    leverage = Column(Integer, nullable=True)
    reduce_only = Column(Integer, nullable=False, server_default='0')
    time_in_force = Column(String(20), nullable=True, server_default='GTC')
    exchange_order_id = Column(String(100), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    submitted_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_orders_trade_id', 'trade_id'),
        Index('idx_orders_exchange_symbol', 'exchange', 'symbol'),
        Index('idx_orders_status_created', 'status', 'created_at'),
    )


class ExecutionLogs(Base):
    """Detailed logs of execution attempts and API responses."""
    __tablename__ = 'execution_logs'

    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=True, index=True)
    order_id = Column(String(36), ForeignKey('orders.id'), nullable=True, index=True)
    action = Column(String(50), nullable=False)  # 'ORDER_SUBMITTED', 'ORDER_FILLED', etc.
    exchange = Column(String(20), nullable=False)
    symbol = Column(String(20), nullable=False)
    request_payload = Column(Text, nullable=True)  # JSON
    response_payload = Column(Text, nullable=True)  # JSON
    status = Column(String(20), nullable=False)  # 'SUCCESS', 'FAILED', 'RETRY'
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default='0')

    __table_args__ = (
        Index('idx_execution_logs_trade', 'trade_id'),
        Index('idx_execution_logs_timestamp', 'timestamp'),
    )


class RiskEvents(Base):
    """Records of risk checks and violations."""
    __tablename__ = 'risk_events'

    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)  # 'VALIDATION_PASSED', 'VIOLATION', etc.
    risk_level = Column(String(20), nullable=False)  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=True)  # Risk metrics snapshot
    action_taken = Column(String(100), nullable=True)  # 'APPROVED', 'REJECTED', 'FLAGGED'
    validator_version = Column(String(20), nullable=True)

    __table_args__ = (
        Index('idx_risk_events_trade', 'trade_id'),
        Index('idx_risk_events_type', 'event_type'),
    )


class RecoveryEvents(Base):
    """Logs of reconciliation actions taken."""
    __tablename__ = 'recovery_events'

    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    recovery_type = Column(String(50), nullable=False)  # 'GHOST_POSITION', 'ORPHANED_ORDER', etc.
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    old_state = Column(Text, nullable=True)  # JSON
    new_state = Column(Text, nullable=True)  # JSON
    auto_repaired = Column(Integer, nullable=False, server_default='0')
    requires_manual_review = Column(Integer, nullable=False, server_default='0')
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=True, index=True)

    __table_args__ = (
        Index('idx_recovery_events_type', 'recovery_type'),
        Index('idx_recovery_events_timestamp', 'timestamp'),
    )


class Signals(Base):
    """Input signals that triggered trades."""
    __tablename__ = 'signals'

    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    source = Column(String(50), nullable=False)  # 'AI_AGENT', 'TECHNICAL_INDICATOR', etc.
    symbol = Column(String(20), nullable=False)
    signal_type = Column(String(20), nullable=False)  # 'ENTRY_LONG', 'ENTRY_SHORT', 'EXIT'
    strength = Column(Float, nullable=False)  # 0.0 to 1.0
    indicators_json = Column(Text, nullable=True)  # Technical indicators snapshot
    regime = Column(String(50), nullable=True)  # Market regime
    confidence = Column(Float, nullable=True)
    trade_id = Column(String(36), ForeignKey('trades.id'), nullable=True, index=True)
    processed = Column(Integer, nullable=False, server_default='0')

    __table_args__ = (
        Index('idx_signals_symbol_time', 'symbol', 'timestamp'),
        Index('idx_signals_trade', 'trade_id'),
    )
