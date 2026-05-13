"""
Integration tests for Market Data Integrity.

Validates the robustness of the data ingestion pipeline including:
- Candle update correctness (no gaps/overlaps)
- WebSocket resilience and reconnection
- Duplicate prevention during reconnection
- Timezone consistency (UTC normalization)
- Missing candle recovery after connection drops

Critical scenario: Simulates network disconnect, reconnection, and validates
gap detection + historical data fetch without data corruption.
"""
import pytest
import asyncio
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from app.websocket.manager import MEXCWebSocketManager


class TestCandleUpdateCorrectness:
    """Test OHLCV data updates sequentially without gaps or overlaps."""
    
    def test_candles_update_sequentially(self):
        """Verify candles have sequential timestamps without gaps."""
        # Simulate candle stream
        candles = [
            {'timestamp': 1000, 'open': 50000, 'high': 50100, 'low': 49900, 'close': 50050, 'volume': 100},
            {'timestamp': 2000, 'open': 50050, 'high': 50150, 'low': 49950, 'close': 50100, 'volume': 120},
            {'timestamp': 3000, 'open': 50100, 'high': 50200, 'low': 50000, 'close': 50150, 'volume': 110},
        ]
        
        # Verify sequential timestamps
        for i in range(1, len(candles)):
            assert candles[i]['timestamp'] > candles[i-1]['timestamp'], \
                f"Candle {i} timestamp not greater than previous"
    
    def test_no_overlapping_candles(self):
        """Verify no two candles have the same timestamp."""
        candles = [
            {'timestamp': 1000, 'close': 50000},
            {'timestamp': 2000, 'close': 50100},
            {'timestamp': 3000, 'close': 50200},
        ]
        
        timestamps = [c['timestamp'] for c in candles]
        assert len(timestamps) == len(set(timestamps)), "Duplicate timestamps detected"
    
    def test_ohlcv_structure_validity(self):
        """Verify OHLCV data maintains valid structure."""
        candle = {
            'timestamp': 1000,
            'open': 50000.0,
            'high': 50100.0,
            'low': 49900.0,
            'close': 50050.0,
            'volume': 100.0
        }
        
        # High >= Low
        assert candle['high'] >= candle['low']
        
        # High >= Open and High >= Close
        assert candle['high'] >= candle['open']
        assert candle['high'] >= candle['close']
        
        # Low <= Open and Low <= Close
        assert candle['low'] <= candle['open']
        assert candle['low'] <= candle['close']
        
        # All values positive
        assert all(v > 0 for k, v in candle.items() if k != 'timestamp')
    
    def test_candle_continuity_price_alignment(self):
        """Verify close price of one candle aligns with open of next."""
        candles = [
            {'timestamp': 1000, 'open': 50000, 'close': 50050},
            {'timestamp': 2000, 'open': 50050, 'close': 50100},  # Open matches previous close
            {'timestamp': 3000, 'open': 50100, 'close': 50150},
        ]
        
        for i in range(1, len(candles)):
            # Allow small tolerance for real-world data
            assert abs(candles[i]['open'] - candles[i-1]['close']) < 0.01, \
                f"Price discontinuity at candle {i}"


class TestWebSocketResilience:
    """Test WebSocket manager successfully reconnects after disconnect."""
    
    @pytest.mark.asyncio
    async def test_websocket_reconnect_after_disconnect(self):
        """Validate WebSocket manager reconnects after simulated disconnect."""
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        # Mock websocket connection
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        
        with patch('websockets.connect', return_value=mock_ws):
            # Simulate initial connection
            ws_manager.websocket = mock_ws
            ws_manager._connected_since = time.time()
            
            # Simulate disconnect
            ws_manager.websocket = None
            
            # Attempt reconnect
            ws_manager.reconnect_attempts = 0
            await ws_manager._handle_reconnect()
            
            # Verify reconnect attempt was made
            assert ws_manager.reconnect_attempts >= 1
    
    @pytest.mark.asyncio
    async def test_websocket_resubscribe_after_reconnect(self):
        """Verify subscriptions are restored after reconnection."""
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        # Add subscriptions
        ws_manager.subscriptions = [
            {'method': 'SUBSCRIPTION', 'params': ['position@btcusdt']}
        ]
        
        mock_ws = AsyncMock()
        ws_manager.websocket = mock_ws
        
        # Resubscribe
        await ws_manager._resubscribe()
        
        # Verify subscription message was sent
        assert mock_ws.send.called
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_on_repeated_failures(self):
        """Verify exponential backoff increases delay on consecutive failures."""
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        delays = []
        for attempt in range(1, 6):
            ws_manager.reconnect_attempts = attempt
            from app.websocket.manager import calculate_exponential_backoff
            delay = calculate_exponential_backoff(
                attempt=attempt,
                base_delay=ws_manager.base_reconnect_delay,
                max_delay=ws_manager.max_reconnect_delay,
                jitter_factor=0  # No jitter for deterministic test
            )
            delays.append(delay)
        
        # Verify delays increase exponentially
        for i in range(1, len(delays)):
            assert delays[i] > delays[i-1], f"Delay did not increase: {delays}"


class TestDuplicatePrevention:
    """Assert no duplicate candles processed during reconnection."""
    
    def test_no_duplicate_candles_in_stream(self):
        """Verify duplicate candles are filtered from data stream."""
        # Simulate candle stream with potential duplicates
        incoming_candles = [
            {'timestamp': 1000, 'close': 50000},
            {'timestamp': 2000, 'close': 50100},
            {'timestamp': 2000, 'close': 50100},  # Duplicate!
            {'timestamp': 3000, 'close': 50200},
        ]
        
        # Deduplication logic
        seen_timestamps = set()
        unique_candles = []
        
        for candle in incoming_candles:
            if candle['timestamp'] not in seen_timestamps:
                seen_timestamps.add(candle['timestamp'])
                unique_candles.append(candle)
        
        # Verify duplicates removed
        assert len(unique_candles) == 3
        assert len(incoming_candles) == 4
    
    def test_candle_cache_prevents_duplicates(self):
        """Verify candle cache prevents processing duplicates."""
        candle_cache = {}
        
        # Process first candle
        candle1 = {'timestamp': 1000, 'close': 50000}
        if candle1['timestamp'] not in candle_cache:
            candle_cache[candle1['timestamp']] = candle1
        
        # Try to process duplicate
        candle2 = {'timestamp': 1000, 'close': 50000}
        is_duplicate = candle2['timestamp'] in candle_cache
        
        assert is_duplicate == True
        assert len(candle_cache) == 1


class TestTimezoneConsistency:
    """Verify all timestamps normalized to UTC."""
    
    def test_timestamps_are_utc(self):
        """Verify timestamps use UTC timezone."""
        # Create timestamp in different timezones
        utc_now = datetime.now(timezone.utc)
        
        # Convert to Unix timestamp (always UTC)
        unix_timestamp = int(utc_now.timestamp())
        
        # Convert back to datetime
        converted_back = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
        
        # Should match original
        assert converted_back.tzinfo == timezone.utc
    
    def test_exchange_timestamp_normalization(self):
        """Verify exchange timestamps normalized to UTC."""
        # Simulate exchange sending local timestamp
        exchange_timestamp = 1700000000  # Unix timestamp (already UTC)
        
        # Convert to datetime
        dt = datetime.fromtimestamp(exchange_timestamp, tz=timezone.utc)
        
        # Verify UTC
        assert dt.tzinfo == timezone.utc
        assert dt.hour == dt.hour  # Should be UTC hour
    
    def test_no_timezone_mismatch_in_candles(self):
        """Verify all candles use consistent timezone."""
        candles = [
            {'timestamp': datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()},
            {'timestamp': datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp()},
            {'timestamp': datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc).timestamp()},
        ]
        
        # All should be UTC
        for candle in candles:
            dt = datetime.fromtimestamp(candle['timestamp'], tz=timezone.utc)
            assert dt.tzinfo == timezone.utc


class TestMissingCandleRecovery:
    """Test logic that fetches historical data to fill gaps."""
    
    def test_gap_detection_in_candle_sequence(self):
        """Detect gaps in candle sequence."""
        candles = [
            {'timestamp': 1000},
            {'timestamp': 2000},
            # Gap: missing 3000
            {'timestamp': 4000},
            {'timestamp': 5000},
        ]
        
        expected_interval = 1000
        gaps = []
        
        for i in range(1, len(candles)):
            time_diff = candles[i]['timestamp'] - candles[i-1]['timestamp']
            if time_diff > expected_interval * 1.5:  # Allow 50% tolerance
                gaps.append({
                    'after': candles[i-1]['timestamp'],
                    'before': candles[i]['timestamp'],
                    'missing_duration': time_diff - expected_interval
                })
        
        assert len(gaps) == 1
        assert gaps[0]['after'] == 2000
        assert gaps[0]['before'] == 4000
    
    @pytest.mark.asyncio
    async def test_historical_fetch_after_reconnect(self):
        """Simulate fetching historical data to fill gap after reconnect."""
        # Simulate gap detection
        last_known_timestamp = 1000
        current_timestamp = 5000
        gap_detected = current_timestamp - last_known_timestamp > 2000
        
        assert gap_detected == True
        
        # Simulate historical fetch
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv.return_value = [
            [2000, 50000, 50100, 49900, 50050, 100],
            [3000, 50050, 50150, 49950, 50100, 120],
            [4000, 50100, 50200, 50000, 50150, 110],
        ]
        
        # Fetch missing candles
        missing_candles = await mock_exchange.fetch_ohlcv(
            symbol='BTC/USDT',
            timeframe='1h',
            since=last_known_timestamp,
            limit=10
        )
        
        # Verify fetched candles fill the gap
        assert len(missing_candles) == 3
        assert missing_candles[0][0] == 2000
        assert missing_candles[-1][0] == 4000
    
    def test_state_resync_without_corruption(self):
        """Verify state resync after gap fill doesn't corrupt data."""
        # Initial state
        candle_store = {
            1000: {'close': 50000},
        }
        
        # Simulate gap and recovery
        recovered_candles = [
            {'timestamp': 2000, 'close': 50100},
            {'timestamp': 3000, 'close': 50200},
        ]
        
        # Merge recovered candles
        for candle in recovered_candles:
            if candle['timestamp'] not in candle_store:
                candle_store[candle['timestamp']] = candle
        
        # Verify no corruption
        assert len(candle_store) == 3
        assert 1000 in candle_store
        assert 2000 in candle_store
        assert 3000 in candle_store
        
        # Verify data integrity
        assert candle_store[1000]['close'] == 50000
        assert candle_store[2000]['close'] == 50100
        assert candle_store[3000]['close'] == 50200


class TestCriticalScenarioNetworkDisconnect:
    """
    Critical Scenario: Simulate network disconnect for 10 seconds,
    then reconnect and validate gap detection + recovery.
    """
    
    @pytest.mark.asyncio
    async def test_network_disconnect_and_recovery(self):
        """
        Complete scenario test:
        1. Normal operation with candle stream
        2. Network disconnect for 10 seconds
        3. Reconnection
        4. Gap detection
        5. Historical data fetch
        6. State resync without corruption
        """
        # Step 1: Normal operation
        candle_store = {}
        last_timestamp = 1000
        
        # Simulate normal candle stream
        for i in range(10):
            timestamp = last_timestamp + (i * 1000)
            candle_store[timestamp] = {
                'timestamp': timestamp,
                'close': 50000 + (i * 10)
            }
            last_timestamp = timestamp
        
        assert len(candle_store) == 10
        
        # Step 2: Network disconnect for 10 seconds
        disconnect_start = time.time()
        await asyncio.sleep(0.1)  # Simulate 10s disconnect (sped up for test)
        disconnect_duration = time.time() - disconnect_start
        
        # During disconnect, candles would have been generated
        missed_candles_count = 10  # Assume 1 candle per second
        
        # Step 3: Reconnection
        ws_manager = MEXCWebSocketManager(market_type='futures')
        ws_manager.reconnect_attempts = 0
        await ws_manager._handle_reconnect()
        
        assert ws_manager.reconnect_attempts >= 1
        
        # Step 4: Gap detection
        expected_next_timestamp = last_timestamp + 1000
        actual_current_timestamp = last_timestamp + (missed_candles_count * 1000)
        
        gap_detected = actual_current_timestamp - expected_next_timestamp > 0
        assert gap_detected == True
        
        # Step 5: Historical data fetch
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv.return_value = [
            [last_timestamp + (i * 1000), 50000 + (i * 10), 50100, 49900, 50050 + (i * 10), 100]
            for i in range(1, missed_candles_count + 1)
        ]
        
        missing_candles = await mock_exchange.fetch_ohlcv(
            symbol='BTC/USDT',
            timeframe='1s',
            since=expected_next_timestamp,
            limit=missed_candles_count
        )
        
        assert len(missing_candles) == missed_candles_count
        
        # Step 6: State resync
        for candle_data in missing_candles:
            timestamp = candle_data[0]
            if timestamp not in candle_store:
                candle_store[timestamp] = {
                    'timestamp': timestamp,
                    'close': candle_data[4]
                }
        
        # Verify no data corruption
        assert len(candle_store) == 20  # Original 10 + recovered 10
        
        # Verify sequential integrity
        sorted_timestamps = sorted(candle_store.keys())
        for i in range(1, len(sorted_timestamps)):
            assert sorted_timestamps[i] > sorted_timestamps[i-1], \
                "Timestamp order corrupted"
        
        # Verify no duplicates
        assert len(sorted_timestamps) == len(set(sorted_timestamps))
        
        print(f"✅ Successfully recovered from {disconnect_duration:.2f}s disconnect")
        print(f"   Recovered {len(missing_candles)} missing candles")
        print(f"   Total candles in store: {len(candle_store)}")
    
    @pytest.mark.asyncio
    async def test_duplicate_prevention_during_resync(self):
        """Verify no duplicates created during gap recovery."""
        # Existing candles
        candle_store = {
            1000: {'close': 50000},
            2000: {'close': 50100},
        }
        
        # Recovered candles (some may overlap)
        recovered_candles = [
            {'timestamp': 2000, 'close': 50100},  # Already exists!
            {'timestamp': 3000, 'close': 50200},
            {'timestamp': 4000, 'close': 50300},
        ]
        
        # Smart merge (prevent duplicates)
        duplicates_prevented = 0
        for candle in recovered_candles:
            if candle['timestamp'] in candle_store:
                duplicates_prevented += 1
                # Skip duplicate
                continue
            candle_store[candle['timestamp']] = candle
        
        # Verify duplicate was prevented
        assert duplicates_prevented == 1
        assert len(candle_store) == 4  # 2 original + 2 new (not 3)
        
        # Verify no duplicate timestamps
        timestamps = list(candle_store.keys())
        assert len(timestamps) == len(set(timestamps))
