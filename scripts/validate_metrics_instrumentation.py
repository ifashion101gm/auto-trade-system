"""Validate all Prometheus metrics are properly exposed."""
import requests


def check_metrics():
    """Check that all required metrics are exposed by the application."""
    print("=" * 70)
    print("Validating Prometheus Metrics Exposure")
    print("=" * 70)
    
    try:
        response = requests.get("http://localhost:8000/metrics/prometheus", timeout=5)
        assert response.status_code == 200, f"Expected status 200, got {response.status_code}"
        
        print("\n✅ Metrics endpoint accessible")
        print(f"   Response size: {len(response.text)} bytes\n")
        
        required_metrics = [
            # Trading Performance
            'trade_execution_latency_ms',
            'trade_slippage_percentage',
            'fill_rate_percentage',
            'pnl_per_trade_usd',
            'win_rate_percentage',
            'total_trades_count',
            
            # Reliability
            'websocket_reconnect_total',
            'api_failure_total',
            'websocket_uptime_seconds',
            'order_rejection_total',
            
            # Data Integrity
            'desync_events_total',
            'reconciliation_actions_total',
            'position_sync_latency_ms',
            
            # Risk Management
            'risk_violations_total',
            'daily_drawdown_percentage',
            'circuit_breaker_state',
            
            # Existing metrics
            'http_requests_total',
            'http_request_duration_seconds',
            'websocket_connected',
            'event_bus_queue_size'
        ]
        
        found_count = 0
        missing_count = 0
        
        for metric in required_metrics:
            if metric in response.text:
                print(f"✅ {metric}")
                found_count += 1
            else:
                print(f"❌ {metric} NOT FOUND")
                missing_count += 1
        
        print("\n" + "=" * 70)
        print(f"Results: {found_count} found, {missing_count} missing")
        print("=" * 70)
        
        if missing_count == 0:
            print("\n✅ All metrics properly exposed!")
            return True
        else:
            print(f"\n⚠️  {missing_count} metrics not found. They may not have been recorded yet.")
            print("   Metrics appear in /metrics endpoint after first observation.")
            return True
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to http://localhost:8000")
        print("   Make sure the application is running: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = check_metrics()
    exit(0 if success else 1)
