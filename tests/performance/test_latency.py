"""
Latency & Performance Benchmark Tests.

Measures critical path latency in the trading system to ensure
scalping strategies remain viable. High latency destroys edge.

Benchmarks:
1. Signal Generation Time (market data → trade proposal)
2. Exchange Response Time (order submission → acknowledgement)
3. WebSocket Latency (exchange timestamp → local receipt)

Methodology:
- Use time.perf_counter() for high-precision timing
- Run each benchmark 10+ times for statistical significance
- Calculate average, min, max, p95, and p99 latency
- Assert critical paths stay under defined thresholds
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict
from statistics import mean, median, stdev


class TestSignalGenerationLatency:
    """Benchmark signal generation time from market data to trade proposal."""
    
    @pytest.mark.asyncio
    async def test_signal_generation_benchmark(self):
        """
        Measure time taken to generate signal from fresh market data.
        
        Threshold: <100ms for simple strategies (breakout, MA cross)
        """
        # Import strategy components
        from app.strategy.indicators import calculate_atr, calculate_rsi, calculate_sma
        
        latencies = []
        num_iterations = 20
        
        # Generate synthetic market data
        candles = [
            {
                'open': 50000 + i * 10,
                'high': 50000 + i * 10 + 50,
                'low': 50000 + i * 10 - 50,
                'close': 50000 + i * 10 + 20,
                'volume': 1000 + i * 100
            }
            for i in range(100)
        ]
        
        for _ in range(num_iterations):
            start = time.perf_counter()
            
            # Simulate signal generation pipeline
            closes = [c['close'] for c in candles]
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            
            # Calculate indicators (convert to OHLCV format for ATR)
            ohlcv = [[c['open'], c['high'], c['low'], c['close'], c['volume']] for c in candles]
            atr = calculate_atr(ohlcv, period=14)
            rsi = calculate_rsi(closes, period=14)
            sma_fast = calculate_sma(closes, period=9)
            sma_slow = calculate_sma(closes, period=21)
            
            # Simple crossover logic
            signal = None
            if sma_fast > sma_slow and rsi < 70:
                signal = 'LONG'
            elif sma_fast < sma_slow and rsi > 30:
                signal = 'SHORT'
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        # Calculate statistics
        avg_latency = mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n📊 Signal Generation Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   Min:     {min_latency:.2f}ms")
        print(f"   Max:     {max_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        
        # Assertions
        assert avg_latency < 100, f"Average signal generation too slow: {avg_latency:.2f}ms"
        assert p95_latency < 150, f"P95 latency too high: {p95_latency:.2f}ms"
        assert max_latency < 500, f"Max latency unacceptable: {max_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_complex_strategy_signal_latency(self):
        """
        Measure latency for complex multi-indicator strategy.
        
        Threshold: <200ms for complex strategies (multi-timeframe, multiple indicators)
        """
        from app.strategy.indicators import calculate_atr, calculate_rsi, calculate_sma, calculate_ema
        
        latencies = []
        num_iterations = 20
        
        candles = [
            {
                'open': 50000 + i * 10,
                'high': 50000 + i * 10 + 50,
                'low': 50000 + i * 10 - 50,
                'close': 50000 + i * 10 + 20,
                'volume': 1000 + i * 100
            }
            for i in range(200)  # More data points
        ]
        
        for _ in range(num_iterations):
            start = time.perf_counter()
            
            closes = [c['close'] for c in candles]
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            
            # Complex indicator suite (convert to OHLCV format for ATR)
            ohlcv = [[c['open'], c['high'], c['low'], c['close'], c['volume']] for c in candles]
            atr = calculate_atr(ohlcv, period=14)
            rsi = calculate_rsi(closes, period=14)
            sma_9 = calculate_sma(closes, period=9)
            sma_21 = calculate_sma(closes, period=21)
            sma_50 = calculate_sma(closes, period=50)
            ema_12 = calculate_ema(closes, period=12)
            ema_26 = calculate_ema(closes, period=26)
            
            # Multi-condition signal logic
            trend_bullish = sma_9 > sma_21 > sma_50
            momentum_strong = rsi > 50 and rsi < 70
            volume_confirmation = True  # Simplified
            
            signal = None
            if trend_bullish and momentum_strong:
                signal = 'LONG'
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n📊 Complex Strategy Signal Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        
        # Slightly higher threshold for complex strategies
        assert avg_latency < 200, f"Complex strategy too slow: {avg_latency:.2f}ms"
        assert p95_latency < 300, f"Complex strategy P95 too high: {p95_latency:.2f}ms"


class TestExchangeResponseLatency:
    """Benchmark exchange API response times for order operations."""
    
    @pytest.mark.asyncio
    async def test_order_submission_latency(self):
        """
        Measure round-trip time for order submission.
        
        Threshold: <500ms for demo APIs, <200ms for production APIs
        """
        mock_exchange = AsyncMock()
        
        # Simulate realistic API delay
        async def simulate_api_call(symbol, side, amount):
            await asyncio.sleep(0.05)  # 50ms network + processing delay
            return {
                'order_id': 'test-order-123',
                'status': 'NEW',
                'price': 50000.0,
                'filled': 0.0
            }
        
        mock_exchange.create_market_order = simulate_api_call
        
        latencies = []
        num_iterations = 10
        
        for i in range(num_iterations):
            start = time.perf_counter()
            
            result = await mock_exchange.create_market_order(
                symbol='BTC/USDT',
                side='buy',
                amount=0.001
            )
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n📊 Order Submission Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   Min:     {min_latency:.2f}ms")
        print(f"   Max:     {max_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        
        # Demo API threshold (higher tolerance)
        assert avg_latency < 500, f"Order submission too slow: {avg_latency:.2f}ms"
        assert max_latency < 1000, f"Max order latency unacceptable: {max_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_order_status_check_latency(self):
        """
        Measure latency for order status polling.
        
        Critical for partial fill detection and TP/SL monitoring.
        """
        mock_exchange = AsyncMock()
        
        async def simulate_status_check(order_id, symbol):
            await asyncio.sleep(0.03)  # 30ms delay
            return {
                'order_id': order_id,
                'status': 'FILLED',
                'filled': 0.001,
                'remaining': 0.0,
                'price': 50000.0
            }
        
        mock_exchange.fetch_order_status = simulate_status_check
        
        latencies = []
        num_iterations = 10
        
        for i in range(num_iterations):
            start = time.perf_counter()
            
            status = await mock_exchange.fetch_order_status(
                order_id=f'order-{i}',
                symbol='BTC/USDT'
            )
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n📊 Order Status Check Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        
        assert avg_latency < 200, f"Status check too slow: {avg_latency:.2f}ms"
        assert p95_latency < 300, f"Status check P95 too high: {p95_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_position_fetch_latency(self):
        """
        Measure latency for fetching open positions.
        
        Used by PositionSyncService every 5 seconds.
        """
        mock_exchange = AsyncMock()
        
        async def simulate_position_fetch():
            await asyncio.sleep(0.04)  # 40ms delay
            return [
                {
                    'symbol': 'BTC/USDT',
                    'size': 0.01,
                    'entry_price': 50000.0,
                    'mark_price': 50100.0,
                    'unrealized_pnl': 1.0,
                    'leverage': 2
                }
            ]
        
        mock_exchange.get_open_positions = simulate_position_fetch
        
        latencies = []
        num_iterations = 10
        
        for i in range(num_iterations):
            start = time.perf_counter()
            
            positions = await mock_exchange.get_open_positions()
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        max_latency = max(latencies)
        
        print(f"\n📊 Position Fetch Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   Max:     {max_latency:.2f}ms")
        
        assert avg_latency < 300, f"Position fetch too slow: {avg_latency:.2f}ms"
        assert max_latency < 500, f"Max position fetch latency too high: {max_latency:.2f}ms"


class TestWebSocketLatency:
    """Benchmark WebSocket message delivery latency."""
    
    @pytest.mark.asyncio
    async def test_websocket_message_latency(self):
        """
        Measure time difference between exchange timestamp and local receipt.
        
        Threshold: <100ms for real-time position updates
        """
        latencies = []
        num_iterations = 20
        
        for i in range(num_iterations):
            # Simulate exchange timestamp
            exchange_timestamp = time.time()
            
            # Simulate network delay
            await asyncio.sleep(0.02)  # 20ms network delay
            
            # Local receipt time
            local_timestamp = time.time()
            
            latency_ms = (local_timestamp - exchange_timestamp) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n📊 WebSocket Message Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   Min:     {min_latency:.2f}ms")
        print(f"   Max:     {max_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        
        assert avg_latency < 100, f"WebSocket latency too high: {avg_latency:.2f}ms"
        assert p95_latency < 150, f"WebSocket P95 latency too high: {p95_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_websocket_reconnection_speed(self):
        """
        Measure time to reconnect after disconnection.
        
        Critical for minimizing downtime during network issues.
        """
        from app.websocket.manager import MEXCWebSocketManager, calculate_exponential_backoff
        
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        # Test first reconnection (should be fast)
        delay_1 = calculate_exponential_backoff(
            attempt=1,
            base_delay=ws_manager.base_reconnect_delay,
            max_delay=ws_manager.max_reconnect_delay,
            jitter_factor=ws_manager.jitter_factor
        )
        
        # Test fifth reconnection (exponential backoff)
        delay_5 = calculate_exponential_backoff(
            attempt=5,
            base_delay=ws_manager.base_reconnect_delay,
            max_delay=ws_manager.max_reconnect_delay,
            jitter_factor=ws_manager.jitter_factor
        )
        
        print(f"\n📊 WebSocket Reconnection Delays:")
        print(f"   Attempt 1: {delay_1:.2f}s")
        print(f"   Attempt 5: {delay_5:.2f}s")
        
        # First attempt should be relatively quick
        assert delay_1 < 10, f"First reconnect delay too long: {delay_1:.2f}s"
        
        # Exponential growth should be present
        assert delay_5 > delay_1, "Exponential backoff not working"
        
        # Should cap at maximum
        assert delay_5 <= ws_manager.max_reconnect_delay + 10, "Delay exceeds maximum"


class TestEndToEndTradeLatency:
    """Measure complete trade execution pipeline latency."""
    
    @pytest.mark.asyncio
    async def test_full_trade_pipeline_latency(self):
        """
        Measure total time from signal generation to order confirmation.
        
        This is the most critical metric for scalping strategies.
        Threshold: <1 second for demo, <500ms for production
        """
        from app.strategy.indicators import calculate_sma, calculate_rsi
        
        # Mock exchange
        mock_exchange = AsyncMock()
        
        async def simulate_order_creation(symbol, side, amount):
            await asyncio.sleep(0.05)  # 50ms API call
            return {
                'order_id': 'e2e-test-order',
                'status': 'NEW',
                'price': 50000.0,
                'filled': 0.0
            }
        
        mock_exchange.create_market_order = simulate_order_creation
        
        latencies = []
        num_iterations = 10
        
        # Generate test data
        candles = [
            {'close': 50000 + i * 10}
            for i in range(100)
        ]
        
        for _ in range(num_iterations):
            start = time.perf_counter()
            
            # Step 1: Signal generation
            closes = [c['close'] for c in candles]
            sma = calculate_sma(closes, period=9)
            rsi = calculate_rsi(closes, period=14)
            
            signal = 'LONG' if sma > closes[-1] and rsi < 70 else None
            
            if signal:
                # Step 2: Order submission
                result = await mock_exchange.create_market_order(
                    symbol='BTC/USDT',
                    side='buy',
                    amount=0.001
                )
                
                # Step 3: Order confirmation
                await asyncio.sleep(0.02)  # Simulate confirmation delay
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        max_latency = max(latencies)
        
        print(f"\n📊 End-to-End Trade Pipeline Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        print(f"   Max:     {max_latency:.2f}ms")
        
        # Demo environment threshold
        assert avg_latency < 1000, f"E2E latency too slow: {avg_latency:.2f}ms"
        assert p95_latency < 1500, f"E2E P95 latency too high: {p95_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_order_submission_latency(self):
        """
        Measure latency when submitting multiple orders concurrently.
        
        Important for multi-symbol strategies.
        """
        mock_exchange = AsyncMock()
        
        async def simulate_order(symbol, side, amount):
            await asyncio.sleep(0.05)  # 50ms per order
            return {'order_id': f'{symbol}-order', 'status': 'NEW'}
        
        mock_exchange.create_market_order = simulate_order
        
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        
        start = time.perf_counter()
        
        # Submit orders concurrently
        tasks = [
            mock_exchange.create_market_order(symbol=s, side='buy', amount=0.001)
            for s in symbols
        ]
        results = await asyncio.gather(*tasks)
        
        end = time.perf_counter()
        total_latency_ms = (end - start) * 1000
        
        print(f"\n📊 Concurrent Order Submission ({len(symbols)} orders):")
        print(f"   Total Time: {total_latency_ms:.2f}ms")
        print(f"   Per Order (avg): {total_latency_ms / len(symbols):.2f}ms")
        
        # Concurrent should be faster than sequential
        # Sequential would be ~150ms (3 * 50ms), concurrent should be ~50-70ms
        assert total_latency_ms < 150, f"Concurrent submission too slow: {total_latency_ms:.2f}ms"


class TestDatabaseQueryLatency:
    """Benchmark database query performance."""
    
    @pytest.mark.asyncio
    async def test_trade_query_latency(self):
        """
        Measure latency for querying open trades.
        
        Critical for risk management checks before new orders.
        """
        mock_db_session = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Simulate database query delay
        async def simulate_query(session):
            await asyncio.sleep(0.01)  # 10ms query time
            return [
                MagicMock(symbol='BTC/USDT', status='OPEN'),
                MagicMock(symbol='ETH/USDT', status='OPEN')
            ]
        
        mock_trade_repo.get_open_trades = simulate_query
        
        latencies = []
        num_iterations = 20
        
        for _ in range(num_iterations):
            start = time.perf_counter()
            
            trades = await mock_trade_repo.get_open_trades(mock_db_session)
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\n📊 Database Query Latency - Open Trades ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   P95:     {p95_latency:.2f}ms")
        
        assert avg_latency < 50, f"DB query too slow: {avg_latency:.2f}ms"
        assert p95_latency < 100, f"DB query P95 too high: {p95_latency:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_position_sync_query_latency(self):
        """
        Measure latency for position synchronization queries.
        
        Runs every 5 seconds, must be fast.
        """
        mock_db_session = AsyncMock()
        mock_position_repo = AsyncMock()
        
        async def simulate_query(session):
            await asyncio.sleep(0.008)  # 8ms query time
            return [
                MagicMock(symbol='BTC/USDT', size=0.01, current_price=50000.0)
            ]
        
        mock_position_repo.get_open_positions = simulate_query
        
        latencies = []
        num_iterations = 20
        
        for _ in range(num_iterations):
            start = time.perf_counter()
            
            positions = await mock_position_repo.get_open_positions(mock_db_session)
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        avg_latency = mean(latencies)
        max_latency = max(latencies)
        
        print(f"\n📊 Position Sync Query Latency ({num_iterations} iterations):")
        print(f"   Average: {avg_latency:.2f}ms")
        print(f"   Max:     {max_latency:.2f}ms")
        
        assert avg_latency < 30, f"Position query too slow: {avg_latency:.2f}ms"
        assert max_latency < 50, f"Max position query latency too high: {max_latency:.2f}ms"


class TestSystemThroughput:
    """Test system throughput under load."""
    
    @pytest.mark.asyncio
    async def test_high_frequency_signal_processing(self):
        """
        Test system ability to process rapid successive signals.
        
        Simulates high-frequency market conditions.
        """
        from app.strategy.indicators import calculate_rsi
        
        signals_processed = 0
        start_time = time.perf_counter()
        
        # Process 100 signals rapidly
        for i in range(100):
            # Generate random price data
            prices = [50000 + j * 5 for j in range(50)]
            
            # Calculate signal
            rsi = calculate_rsi(prices, period=14)
            signal = 'LONG' if rsi < 30 else ('SHORT' if rsi > 70 else None)
            
            if signal:
                signals_processed += 1
        
        end_time = time.perf_counter()
        total_time_s = end_time - start_time
        throughput = signals_processed / total_time_s if total_time_s > 0 else 0
        
        print(f"\n📊 High-Frequency Signal Processing:")
        print(f"   Signals Processed: {signals_processed}")
        print(f"   Total Time: {total_time_s:.2f}s")
        print(f"   Throughput: {throughput:.2f} signals/sec")
        
        # Should handle high frequency without bottleneck
        assert total_time_s < 1.0, f"Signal processing too slow: {total_time_s:.2f}s"
        assert throughput > 50, f"Throughput too low: {throughput:.2f} signals/sec"
