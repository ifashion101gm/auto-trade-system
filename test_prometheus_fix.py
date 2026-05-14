#!/usr/bin/env python3
"""
Test script to verify Prometheus metrics duplication fix.
"""
import sys

print("=" * 60)
print("Testing Prometheus Metrics Duplication Fix")
print("=" * 60)
print()

# Test 1: Import main module (should not raise ValueError)
print("Test 1: Importing app.main...")
try:
    from app.main import CUSTOM_REGISTRY, REQUEST_COUNT, REQUEST_LATENCY
    print("✅ PASS: Module imported successfully")
    print(f"   Custom Registry: {CUSTOM_REGISTRY}")
    print(f"   REQUEST_COUNT: {REQUEST_COUNT}")
except ValueError as e:
    if "Duplicated timeseries" in str(e):
        print(f"❌ FAIL: {e}")
        sys.exit(1)
    else:
        raise
except Exception as e:
    print(f"❌ FAIL: Unexpected error: {e}")
    sys.exit(1)

print()

# Test 2: Verify metrics are registered in custom registry
print("Test 2: Checking metrics registration...")
metrics_in_registry = list(CUSTOM_REGISTRY._names_to_collectors.keys())
print(f"   Metrics in registry: {len(metrics_in_registry)}")
for metric_name in ['http_requests_total', 'http_request_duration_seconds', 
                     'websocket_connected', 'event_bus_queue_size']:
    if metric_name in metrics_in_registry:
        print(f"   ✅ {metric_name}")
    else:
        print(f"   ❌ {metric_name} NOT FOUND")
        sys.exit(1)

print()

# Test 3: Try importing again (simulating reload)
print("Test 3: Simulating module reload...")
try:
    # Force re-import
    import importlib
    import app.main
    importlib.reload(app.main)
    print("✅ PASS: Module reloaded without duplication error")
except ValueError as e:
    if "Duplicated timeseries" in str(e):
        print(f"❌ FAIL: Duplication error on reload: {e}")
        sys.exit(1)
    else:
        raise

print()
print("=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print()
print("The Prometheus metrics duplication issue is FIXED.")
print("You can now start the application without errors.")
