"""Initial migration - Create all VMassit database tables.

Revision ID: 001
Revises: 
Create Date: 2026-05-10 00:00:00.000000

This migration creates the complete database schema for VMassit including:
- Model usage tracking
- Assistant memory
- Decision journal
- Strategy management
- Paper trading
- Backtesting and optimization
- Performance metrics
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create all database tables."""
    
    # Table 1: model_usage - LLM API call tracking
    op.create_table(
        'model_usage',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('model', sa.Text, nullable=False),
        sa.Column('endpoint', sa.Text, nullable=False),
        sa.Column('task_type', sa.Text, nullable=False),
        sa.Column('prompt_tokens', sa.Integer, nullable=False),
        sa.Column('completion_tokens', sa.Integer, nullable=False),
        sa.Column('total_tokens', sa.Integer, nullable=False),
        sa.Column('latency_ms', sa.Float, nullable=False),
        sa.Column('estimated_cost_usd', sa.Float, nullable=False),
    )
    
    # Table 2: assistant_memory - Conversation history
    op.create_table(
        'assistant_memory',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('user_id', sa.Text, nullable=False),
        sa.Column('role', sa.Text, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
    )
    
    # Table 3: decision_journal - AI decision logging
    op.create_table(
        'decision_journal',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('user_id', sa.Text, nullable=False),
        sa.Column('prompt', sa.Text, nullable=False),
        sa.Column('reply', sa.Text, nullable=False),
        sa.Column('task_type', sa.Text, nullable=False),
    )
    
    # Table 4: strategy_registry - Strategy metadata
    op.create_table(
        'strategy_registry',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('strategy_id', sa.Text, nullable=False, unique=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('source', sa.Text, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
    )
    
    # Table 5: strategy_evaluations - Strategy performance scores
    op.create_table(
        'strategy_evaluations',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('strategy_id', sa.Text, nullable=False),
        sa.Column('score', sa.Float, nullable=False),
        sa.Column('metrics_json', sa.Text, nullable=False),
    )
    
    # Table 6: paper_trades - Paper trading execution records
    op.create_table(
        'paper_trades',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts_open', sa.Text, nullable=False),
        sa.Column('ts_close', sa.Text, nullable=True),
        sa.Column('user_id', sa.Text, nullable=False),
        sa.Column('exchange', sa.Text, nullable=False),
        sa.Column('symbol', sa.Text, nullable=False),
        sa.Column('side', sa.Text, nullable=False),
        sa.Column('leverage', sa.Float, nullable=False),
        sa.Column('qty', sa.Float, nullable=False),
        sa.Column('entry_price', sa.Float, nullable=False),
        sa.Column('exit_price', sa.Float, nullable=True),
        sa.Column('stop_loss', sa.Float, nullable=True),
        sa.Column('take_profit', sa.Float, nullable=True),
        sa.Column('profit', sa.Float, nullable=True),
        sa.Column('profit_pct', sa.Float, nullable=True),
        sa.Column('status', sa.Text, nullable=False, server_default='open'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('execution_mode', sa.Text, nullable=True),
    )
    
    # Table 7: trail_events - Trailing stop adjustment history
    op.create_table(
        'trail_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('trade_id', sa.Integer, nullable=False),
        sa.Column('old_stop', sa.Float, nullable=False),
        sa.Column('new_stop', sa.Float, nullable=False),
        sa.Column('current_price', sa.Float, nullable=False),
    )
    
    # Table 8: trade_proposals - Trade signal proposals
    op.create_table(
        'trade_proposals',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('user_id', sa.Text, nullable=False),
        sa.Column('exchange', sa.Text, nullable=False),
        sa.Column('symbol', sa.Text, nullable=False),
        sa.Column('side', sa.Text, nullable=False),
        sa.Column('entry_price', sa.Float, nullable=False),
        sa.Column('stop_loss', sa.Float, nullable=True),
        sa.Column('take_profit', sa.Float, nullable=True),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('strategy_name', sa.Text, nullable=True),
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('ai_metadata', sa.Text, nullable=True),
    )
    
    # Table 9: strategy_parameters - Parameter version control
    op.create_table(
        'strategy_parameters',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('strategy_name', sa.Text, nullable=False),
        sa.Column('symbol', sa.Text, nullable=False),
        sa.Column('timeframe', sa.Text, nullable=False),
        sa.Column('parameter_set', sa.Text, nullable=False),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('is_active', sa.Integer, nullable=False, server_default='0'),
        sa.Column('optimization_run_id', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )
    
    # Table 10: backtest_runs - Backtest results
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('run_id', sa.Text, nullable=False, unique=True),
        sa.Column('strategy_name', sa.Text, nullable=False),
        sa.Column('symbol', sa.Text, nullable=False),
        sa.Column('timeframe', sa.Text, nullable=False),
        sa.Column('start_date', sa.Text, nullable=False),
        sa.Column('end_date', sa.Text, nullable=False),
        sa.Column('initial_capital', sa.Float, nullable=False),
        sa.Column('final_capital', sa.Float, nullable=True),
        sa.Column('total_return_pct', sa.Float, nullable=True),
        sa.Column('sharpe_ratio', sa.Float, nullable=True),
        sa.Column('max_drawdown_pct', sa.Float, nullable=True),
        sa.Column('win_rate', sa.Float, nullable=True),
        sa.Column('profit_factor', sa.Float, nullable=True),
        sa.Column('total_trades', sa.Integer, nullable=True),
        sa.Column('status', sa.Text, nullable=False, server_default='running'),
        sa.Column('ai_decision_log', sa.Text, nullable=True),
    )
    
    # Table 11: optimization_runs - Optimization run tracking
    op.create_table(
        'optimization_runs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('run_id', sa.Text, nullable=False, unique=True),
        sa.Column('strategy_name', sa.Text, nullable=False),
        sa.Column('symbol', sa.Text, nullable=False),
        sa.Column('timeframe', sa.Text, nullable=False),
        sa.Column('optimization_method', sa.Text, nullable=False),
        sa.Column('parameter_space', sa.Text, nullable=False),
        sa.Column('objective_metric', sa.Text, nullable=False),
        sa.Column('num_iterations', sa.Integer, nullable=True),
        sa.Column('best_score', sa.Float, nullable=True),
        sa.Column('best_parameters', sa.Text, nullable=True),
        sa.Column('status', sa.Text, nullable=False, server_default='running'),
        sa.Column('completed_at', sa.Text, nullable=True),
    )
    
    # Table 12: performance_periods - Aggregated performance metrics
    op.create_table(
        'performance_periods',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('period_start', sa.Text, nullable=False),
        sa.Column('period_end', sa.Text, nullable=False),
        sa.Column('strategy_name', sa.Text, nullable=False),
        sa.Column('symbol', sa.Text, nullable=False),
        sa.Column('total_trades', sa.Integer, nullable=False),
        sa.Column('winning_trades', sa.Integer, nullable=False),
        sa.Column('losing_trades', sa.Integer, nullable=False),
        sa.Column('win_rate', sa.Float, nullable=False),
        sa.Column('total_profit', sa.Float, nullable=False),
        sa.Column('avg_profit_per_trade', sa.Float, nullable=False),
        sa.Column('sharpe_ratio', sa.Float, nullable=True),
        sa.Column('sortino_ratio', sa.Float, nullable=True),
        sa.Column('max_drawdown_pct', sa.Float, nullable=True),
        sa.Column('profit_factor', sa.Float, nullable=True),
        sa.Column('expectancy', sa.Float, nullable=True),
        sa.Column('calmar_ratio', sa.Float, nullable=True),
        sa.Column('recovery_factor', sa.Float, nullable=True),
        sa.Column('var_95', sa.Float, nullable=True),
        sa.Column('cvar_95', sa.Float, nullable=True),
        sa.Column('beta', sa.Float, nullable=True),
        sa.Column('alpha', sa.Float, nullable=True),
        sa.Column('avg_trade_duration_hours', sa.Float, nullable=True),
        sa.Column('trade_frequency_per_day', sa.Float, nullable=True),
        sa.Column('avg_holding_period_hours', sa.Float, nullable=True),
    )
    
    # Table 13: optimization_results - Optimization result rankings
    op.create_table(
        'optimization_results',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('ts', sa.Text, nullable=False),
        sa.Column('optimization_run_id', sa.Text, nullable=False),
        sa.Column('rank', sa.Integer, nullable=False),
        sa.Column('parameters', sa.Text, nullable=False),
        sa.Column('score', sa.Float, nullable=False),
        sa.Column('metrics_json', sa.Text, nullable=True),
    )
    
    # Table 14: schema_migrations - Migration version tracking
    op.create_table(
        'schema_migrations',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('version', sa.Text, nullable=False, unique=True),
        sa.Column('applied_at', sa.Text, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
    )
    
    # Create indexes for better query performance
    op.create_index('idx_model_usage_ts', 'model_usage', ['ts'])
    op.create_index('idx_model_usage_model', 'model_usage', ['model'])
    op.create_index('idx_assistant_memory_user_ts', 'assistant_memory', ['user_id', 'ts'])
    op.create_index('idx_decision_journal_user_ts', 'decision_journal', ['user_id', 'ts'])
    op.create_index('idx_strategy_evaluations_strategy', 'strategy_evaluations', ['strategy_id'])
    op.create_index('idx_paper_trades_user_status', 'paper_trades', ['user_id', 'status'])
    op.create_index('idx_paper_trades_symbol', 'paper_trades', ['symbol'])
    op.create_index('idx_paper_trades_ts_open', 'paper_trades', ['ts_open'])
    op.create_index('idx_trail_events_trade', 'trail_events', ['trade_id'])
    op.create_index('idx_trade_proposals_user_status', 'trade_proposals', ['user_id', 'status'])
    op.create_index('idx_strategy_parameters_strategy', 'strategy_parameters', ['strategy_name'])
    op.create_index('idx_backtest_runs_strategy', 'backtest_runs', ['strategy_name'])
    op.create_index('idx_optimization_runs_strategy', 'optimization_runs', ['strategy_name'])
    op.create_index('idx_performance_periods_strategy', 'performance_periods', ['strategy_name'])
    op.create_index('idx_optimization_results_run', 'optimization_results', ['optimization_run_id'])


def downgrade():
    """Drop all database tables (in reverse order)."""
    op.drop_index('idx_optimization_results_run', table_name='optimization_results')
    op.drop_index('idx_performance_periods_strategy', table_name='performance_periods')
    op.drop_index('idx_optimization_runs_strategy', table_name='optimization_runs')
    op.drop_index('idx_backtest_runs_strategy', table_name='backtest_runs')
    op.drop_index('idx_strategy_parameters_strategy', table_name='strategy_parameters')
    op.drop_index('idx_trade_proposals_user_status', table_name='trade_proposals')
    op.drop_index('idx_trail_events_trade', table_name='trail_events')
    op.drop_index('idx_paper_trades_ts_open', table_name='paper_trades')
    op.drop_index('idx_paper_trades_symbol', table_name='paper_trades')
    op.drop_index('idx_paper_trades_user_status', table_name='paper_trades')
    op.drop_index('idx_strategy_evaluations_strategy', table_name='strategy_evaluations')
    op.drop_index('idx_decision_journal_user_ts', table_name='decision_journal')
    op.drop_index('idx_assistant_memory_user_ts', table_name='assistant_memory')
    op.drop_index('idx_model_usage_model', table_name='model_usage')
    op.drop_index('idx_model_usage_ts', table_name='model_usage')
    
    op.drop_table('schema_migrations')
    op.drop_table('optimization_results')
    op.drop_table('performance_periods')
    op.drop_table('optimization_runs')
    op.drop_table('backtest_runs')
    op.drop_table('strategy_parameters')
    op.drop_table('trade_proposals')
    op.drop_table('trail_events')
    op.drop_table('paper_trades')
    op.drop_table('strategy_evaluations')
    op.drop_table('strategy_registry')
    op.drop_table('decision_journal')
    op.drop_table('assistant_memory')
    op.drop_table('model_usage')
