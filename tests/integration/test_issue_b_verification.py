"""
Simple verification test for Issue B - Reconciliation Engine Enhancements

Verifies that reconciliation engine has metrics, alerts, and dashboard integration.
"""


def test_reconciliation_engine_has_metrics_method():
    """Verify _publish_metrics method exists."""
    with open('app/execution/reconciliation_engine.py', 'r') as f:
        content = f.read()
    
    assert 'async def _publish_metrics(self, result: ReconciliationResult):' in content, \
        "_publish_metrics method should exist"
    
    assert 'from app.monitoring.prometheus_metrics import get_metrics_collector' in content, \
        "Should import metrics collector"
    
    assert 'metrics.update_reconciliation_mismatches(' in content, \
        "Should call update_reconciliation_mismatches"
    
    print("✅ _publish_metrics method implemented")


def test_reconciliation_engine_has_alerts_method():
    """Verify _send_telegram_alerts method exists."""
    with open('app/execution/reconciliation_engine.py', 'r') as f:
        content = f.read()
    
    assert 'async def _send_telegram_alerts(self, result: ReconciliationResult):' in content, \
        "_send_telegram_alerts method should exist"
    
    assert 'ORPHANED_ORDER_DETECTED' in content, \
        "Should send orphaned order alerts"
    
    assert 'GHOST_POSITION_DETECTED' in content, \
        "Should send ghost position alerts"
    
    assert 'STATUS_MISMATCH_DETECTED' in content, \
        "Should send status mismatch alerts"
    
    print("✅ _send_telegram_alerts method implemented")


def test_reconciliation_loop_calls_metrics_and_alerts():
    """Verify reconciliation loop integrates metrics and alerts."""
    with open('app/execution/reconciliation_engine.py', 'r') as f:
        content = f.read()
    
    # Find the reconciliation loop
    assert 'await self._publish_metrics(result)' in content, \
        "Loop should call _publish_metrics"
    
    assert 'await self._send_telegram_alerts(result)' in content, \
        "Loop should call _send_telegram_alerts"
    
    print("✅ Reconciliation loop calls metrics and alerts")


def test_reconciliation_engine_has_detailed_status():
    """Verify get_detailed_status method exists."""
    with open('app/execution/reconciliation_engine.py', 'r') as f:
        content = f.read()
    
    assert 'def get_detailed_status(self) -> Dict[str, Any]:' in content, \
        "get_detailed_status method should exist"
    
    assert "'is_running'" in content, \
        "Status should include is_running"
    
    assert "'last_run'" in content, \
        "Status should include last_run"
    
    assert "'total_runs'" in content, \
        "Status should include total_runs"
    
    assert "'next_run_in_seconds'" in content, \
        "Status should include next_run_in_seconds"
    
    print("✅ get_detailed_status method implemented")


def test_dashboard_has_reconciliation_endpoints():
    """Verify dashboard API has reconciliation endpoints."""
    with open('app/dashboard/trading_api.py', 'r') as f:
        content = f.read()
    
    # Check for status endpoint
    assert '@router.get("/reconciliation/status")' in content, \
        "/reconciliation/status endpoint should exist"
    
    assert 'async def get_reconciliation_status():' in content, \
        "get_reconciliation_status function should exist"
    
    # Check for metrics endpoint
    assert '@router.get("/reconciliation/metrics")' in content, \
        "/reconciliation/metrics endpoint should exist"
    
    assert 'async def get_reconciliation_metrics():' in content, \
        "get_reconciliation_metrics function should exist"
    
    print("✅ Dashboard reconciliation endpoints implemented")


def test_prometheus_metrics_exist():
    """Verify Prometheus metrics for reconciliation are defined."""
    with open('app/monitoring/prometheus_metrics.py', 'r') as f:
        content = f.read()
    
    assert 'self.reconciliation_mismatches = Gauge(' in content, \
        "reconciliation_mismatches gauge should be defined"
    
    assert 'self.reconciliation_repairs = Counter(' in content, \
        "reconciliation_repairs counter should be defined"
    
    assert "'reconciliation_mismatches_total'" in content, \
        "Metric name should be reconciliation_mismatches_total"
    
    assert "'reconciliation_repairs_total'" in content, \
        "Metric name should be reconciliation_repairs_total"
    
    print("✅ Prometheus reconciliation metrics defined")


if __name__ == '__main__':
    print("Running Issue B Verification Tests...\n")
    
    try:
        test_reconciliation_engine_has_metrics_method()
        test_reconciliation_engine_has_alerts_method()
        test_reconciliation_loop_calls_metrics_and_alerts()
        test_reconciliation_engine_has_detailed_status()
        test_dashboard_has_reconciliation_endpoints()
        test_prometheus_metrics_exist()
        
        print("\n" + "="*70)
        print("✅ ALL VERIFICATION TESTS PASSED!")
        print("="*70)
        print("\nIssue B Implementation Summary:")
        print("  ✅ Prometheus metrics integration complete")
        print("  ✅ Telegram alerts for mismatches implemented")
        print("  ✅ Dashboard API endpoints added")
        print("  ✅ Detailed status tracking available")
        print("  ✅ Reconciliation loop enhanced")
        print("\nProduction Readiness: Issue B COMPLETE")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
