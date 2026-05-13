# Layer 5: Shadow Mode Architecture

## Overview

Shadow Mode runs the trading bot against **live market data** WITHOUT placing real orders. It simulates order execution locally and compares simulated PnL against actual market movement to validate strategy efficacy and risk management accuracy before live deployment.

This is the final validation layer before going live with real capital.

## Mechanism

### Data Flow

```
┌─────────────────────┐
│ Live WebSocket Data │ (Real-time prices from exchanges)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Signal Generation   │ (Full strategy pipeline runs normally)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Risk Engine Check   │ (Validation only, no database writes)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Local Simulation    │ (NO orders sent to exchanges!)
│ - Apply slippage    │
│ - Track positions   │
│ - Calculate PnL     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Performance Tracking│ (Simulated vs Actual comparison)
└─────────────────────┘
```

### Implementation Components

#### 1. Live Data Ingestion

Use existing WebSocket managers to subscribe to real-time ticker streams:

```python
from app.websocket.mexc_ws_manager import MEXCWebSocketManager
from app.websocket.binance_ws_manager import BinanceWebSocketManager

class ShadowModeDataFeed:
    """Ingest live market data without executing trades."""
    
    def __init__(self):
        self.mexc_ws = MEXCWebSocketManager()
        self.binance_ws = BinanceWebSocketManager()
        self.latest_prices = {}
    
    async def start(self, symbols: List[str]):
        """Subscribe to live price feeds."""
        for symbol in symbols:
            await self.mexc_ws.subscribe_ticker(
                symbol=symbol,
                callback=self._on_price_update
            )
    
    def _on_price_update(self, symbol: str, price: float):
        """Update latest price cache."""
        self.latest_prices[symbol] = {
            'price': price,
            'timestamp': datetime.utcnow()
        }
```

#### 2. Signal Generation

Run full strategy pipeline unchanged:

```python
async def generate_shadow_signals(market_data: Dict) -> List[SignalProposal]:
    """Generate signals using live data (same as production)."""
    manager = StrategyManager()
    signals = await manager.generate_signals(market_data)
    
    # Filter out None signals
    return [s for s in signals if s is not None]
```

#### 3. Simulated Execution Engine

```python
class ShadowExecutor:
    """Simulate order execution without sending to exchanges."""
    
    def __init__(self, slippage_model: str = 'fixed_pct'):
        self.positions = {}
        self.trade_log = []
        self.slippage_model = slippage_model
    
    def simulate_order(self, signal: SignalProposal, current_price: float):
        """
        Simulate order execution with realistic slippage.
        
        Args:
            signal: Trade signal from strategy
            current_price: Current market price
        
        Returns:
            Simulated fill details
        """
        # Apply slippage model
        if self.slippage_model == 'fixed_pct':
            slippage_pct = 0.001  # 0.1% fixed slippage
        elif self.slippage_model == 'volatility_based':
            slippage_pct = self._calculate_volatility_slippage(signal.symbol)
        else:
            slippage_pct = 0.001
        
        # Calculate fill price
        if signal.side == 'LONG':
            fill_price = current_price * (1 + slippage_pct)
        else:  # SHORT
            fill_price = current_price * (1 - slippage_pct)
        
        # Track simulated position
        position_id = f"{signal.symbol}_{datetime.utcnow().timestamp()}"
        self.positions[position_id] = {
            'symbol': signal.symbol,
            'side': signal.side,
            'entry_price': fill_price,
            'quantity': signal.quantity,
            'leverage': signal.leverage,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'timestamp': datetime.utcnow(),
            'strategy': signal.strategy_name
        }
        
        # Log the simulated trade
        self.trade_log.append({
            'position_id': position_id,
            'action': 'OPEN',
            'fill_price': fill_price,
            'expected_slippage': slippage_pct,
            'timestamp': datetime.utcnow()
        })
        
        return {
            'position_id': position_id,
            'fill_price': fill_price,
            'slippage_applied': slippage_pct
        }
    
    def simulate_exit(self, position_id: str, current_price: float, reason: str):
        """
        Simulate position exit (TP/SL hit or manual close).
        
        Args:
            position_id: Position to close
            current_price: Exit price
            reason: 'TAKE_PROFIT', 'STOP_LOSS', or 'MANUAL'
        """
        position = self.positions.get(position_id)
        if not position:
            return None
        
        # Calculate PnL
        if position['side'] == 'LONG':
            pnl = (current_price - position['entry_price']) * position['quantity']
        else:
            pnl = (position['entry_price'] - current_price) * position['quantity']
        
        # Apply leverage
        pnl_with_leverage = pnl * position['leverage']
        
        # Log the exit
        self.trade_log.append({
            'position_id': position_id,
            'action': 'CLOSE',
            'exit_price': current_price,
            'pnl': pnl_with_leverage,
            'reason': reason,
            'timestamp': datetime.utcnow()
        })
        
        # Remove position
        del self.positions[position_id]
        
        return {
            'pnl': pnl_with_leverage,
            'exit_price': current_price,
            'reason': reason
        }
    
    def calculate_shadow_pnl(self, symbol: str, current_price: float) -> float:
        """Calculate unrealized PnL for open positions."""
        total_pnl = 0
        
        for pos_id, position in self.positions.items():
            if position['symbol'] == symbol:
                if position['side'] == 'LONG':
                    pnl = (current_price - position['entry_price']) * position['quantity']
                else:
                    pnl = (position['entry_price'] - current_price) * position['quantity']
                
                total_pnl += pnl * position['leverage']
        
        return total_pnl
```

#### 4. Performance Comparison Engine

```python
class ShadowPerformanceTracker:
    """Track and compare simulated vs actual performance."""
    
    def __init__(self):
        self.shadow_trades = []
        self.actual_market_moves = []
    
    def record_shadow_trade(self, trade: Dict):
        """Record simulated trade."""
        self.shadow_trades.append(trade)
    
    def record_actual_move(self, symbol: str, start_price: float, end_price: float):
        """Record what actually happened in the market."""
        self.actual_market_moves.append({
            'symbol': symbol,
            'start_price': start_price,
            'end_price': end_price,
            'actual_move_pct': (end_price - start_price) / start_price,
            'timestamp': datetime.utcnow()
        })
    
    def calculate_accuracy_score(self) -> float:
        """
        Calculate how closely simulation matched reality.
        
        Returns:
            Accuracy score (0-100%)
        """
        if len(self.shadow_trades) == 0:
            return 0.0
        
        correct_direction = 0
        total_trades = len(self.shadow_trades)
        
        for trade in self.shadow_trades:
            if trade['action'] == 'CLOSE':
                # Check if predicted direction matched actual move
                predicted_direction = 1 if trade['pnl'] > 0 else -1
                
                # Find corresponding actual market move
                actual_move = self._find_actual_move(
                    trade['symbol'],
                    trade['timestamp']
                )
                
                if actual_move:
                    actual_direction = 1 if actual_move['actual_move_pct'] > 0 else -1
                    
                    if predicted_direction == actual_direction:
                        correct_direction += 1
        
        accuracy = (correct_direction / total_trades) * 100
        return accuracy
    
    def get_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        closed_trades = [t for t in self.shadow_trades if t['action'] == 'CLOSE']
        
        if not closed_trades:
            return {}
        
        pnls = [t['pnl'] for t in closed_trades]
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        win_rate = len(winning_trades) / len(closed_trades) * 100
        
        # Calculate Sharpe ratio (simplified)
        avg_pnl = np.mean(pnls)
        std_pnl = np.std(pnls)
        sharpe_ratio = (avg_pnl / std_pnl) if std_pnl > 0 else 0
        
        # Maximum drawdown
        cumulative_pnl = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative_pnl)
        drawdown = (cumulative_pnl - peak) / peak
        max_drawdown = np.min(drawdown) * 100
        
        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl_per_trade': avg_pnl,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'accuracy_score': self.calculate_accuracy_score()
        }
```

## Logging & Tracking

### Database Schema Extension

Create a separate schema for shadow trades to avoid mixing with production data:

```sql
CREATE TABLE shadow_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID,  -- Reference to original signal (optional)
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'LONG' or 'SHORT'
    simulated_entry_price DECIMAL(18, 8) NOT NULL,
    simulated_exit_price DECIMAL(18, 8),
    quantity DECIMAL(18, 8) NOT NULL,
    leverage INTEGER DEFAULT 1,
    simulated_pnl DECIMAL(18, 2),
    actual_market_move DECIMAL(10, 4),  -- What actually happened
    exit_reason VARCHAR(50),  -- 'TAKE_PROFIT', 'STOP_LOSS', 'MANUAL'
    slippage_applied DECIMAL(10, 6),
    timestamp_open TIMESTAMP NOT NULL,
    timestamp_close TIMESTAMP,
    accuracy_score DECIMAL(5, 2),  -- How close simulation matched reality
    strategy_name VARCHAR(50),
    regime VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_shadow_trades_symbol ON shadow_trades(symbol);
CREATE INDEX idx_shadow_trades_timestamp ON shadow_trades(timestamp_open);
```

### Metrics Dashboard

Display real-time shadow mode metrics:

```python
class ShadowModeDashboard:
    """Real-time dashboard for shadow mode monitoring."""
    
    def get_dashboard_data(self) -> Dict:
        """Get current shadow mode status."""
        metrics = self.performance_tracker.get_performance_metrics()
        
        return {
            'mode': 'SHADOW',
            'status': 'ACTIVE',
            'open_positions': len(self.executor.positions),
            'metrics': metrics,
            'uptime': self.get_uptime(),
            'last_signal_time': self.get_last_signal_time(),
            'warnings': self.get_active_warnings()
        }
```

**Dashboard Metrics:**
- Win rate (simulated)
- Average PnL per trade
- Sharpe ratio
- Maximum drawdown
- Accuracy score (simulated vs actual)
- Active positions count
- Total trades executed
- Uptime duration

## Validation Criteria

Before going live with real capital, shadow mode must meet these criteria:

### Minimum Requirements

✅ **Minimum 100 simulated trades** executed  
✅ **Win rate > 55%** (statistically significant edge)  
✅ **Sharpe ratio > 1.5** (good risk-adjusted returns)  
✅ **Maximum drawdown < 10%** (acceptable risk)  
✅ **Accuracy score > 90%** (simulation matches reality)  
✅ **Zero system crashes** during shadow period  
✅ **All risk limits respected** (no violations)  

### Recommended Targets

🎯 Win rate: 60-70%  
🎯 Sharpe ratio: 2.0+  
🎯 Max drawdown: <7%  
🎯 Accuracy score: 95%+  
🎯 Average trade duration: 2-24 hours (not too short/long)  

## Safety Guarantees

### Hard-Coded Guards

```python
class ShadowModeExecutor:
    """Safety-first shadow mode implementation."""
    
    async def execute_order(self, signal: SignalProposal):
        """NEVER send real orders in shadow mode."""
        
        # HARD GUARD: Explicitly prevent real order submission
        if self.mode == 'SHADOW':
            logger.info(f"SHADOW MODE: Simulating order for {signal.symbol}")
            
            # SIMULATE ONLY - NO API CALLS
            fill = self.simulate_order(signal, current_price)
            
            # DO NOT CALL: exchange.create_order()
            # DO NOT CALL: exchange.place_limit_order()
            # DO NOT CALL: ANY exchange method that places orders
            
            return fill
        
        raise RuntimeError("Shadow mode executor cannot place real orders!")
```

### Additional Safeguards

1. **Read-only API keys only** - Cannot place orders even if code bug occurs
2. **Separate database schema** - Shadow trades isolated from production
3. **Clear visual indicators** - Dashboard shows "SHADOW MODE ACTIVE" prominently
4. **Telegram alerts** - Notify when entering/exiting shadow mode
5. **Audit logging** - All simulated actions logged for review
6. **Manual override** - Easy kill switch to stop shadow mode

## Running Shadow Mode

### Configuration

```bash
# .env.shadow
SHADOW_MODE=true
SHADOW_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT
SHADOW_STRATEGIES=breakout,trend_following
SHADOW_MAX_POSITIONS=3
SHADOW_LOG_LEVEL=DEBUG
```

### Start Shadow Mode

```bash
# Start shadow mode bot
python -m app.main --mode shadow

# Or via systemd
sudo systemctl start auto-trade-shadow
```

### Monitor Shadow Mode

```bash
# View real-time metrics
curl http://localhost:8000/api/shadow/metrics

# View active positions
curl http://localhost:8000/api/shadow/positions

# View trade history
curl http://localhost:8000/api/shadow/trades?limit=50
```

### Stop Shadow Mode

```bash
# Graceful shutdown
sudo systemctl stop auto-trade-shadow

# Or send SIGTERM
kill $(pgrep -f "auto-trade.*shadow")
```

## Transition to Live Trading

Once shadow mode validation criteria are met:

1. **Review all shadow trades** - Analyze winners and losers
2. **Verify risk management** - Confirm SL/TP logic worked correctly
3. **Check accuracy score** - Ensure simulation matched reality
4. **Document lessons learned** - Note any unexpected behaviors
5. **Start with small size** - Begin live trading at 10% of intended size
6. **Monitor closely** - Watch first 10-20 live trades carefully
7. **Scale gradually** - Increase position sizes as confidence grows

## Next Steps After Shadow Mode

After successful shadow mode validation:

1. Deploy to **Layer 4: Paper Trading** with demo accounts (if not done already)
2. Execute **50+ paper trades** to validate real API interactions
3. Compare paper trading results with shadow mode predictions
4. If aligned, proceed to **Live Trading** with minimal capital
5. Continue monitoring and iterate on strategies

## Conclusion

Shadow Mode is the critical final validation step before risking real capital. It provides:

- **Confidence**: Strategies work on live data, not just backtests
- **Safety**: No financial risk while validating
- **Insights**: Realistic performance expectations
- **Optimization**: Identify weaknesses before going live

Never skip Shadow Mode. The cost of running it is zero, but the cost of skipping it could be your entire account balance.
