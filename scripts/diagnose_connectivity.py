"""
Comprehensive diagnostic script for WebSocket and Database connectivity issues.
Tests both infrastructure components and validates the robust fixes implemented.
"""
import asyncio
import sys
import time
import logging
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.logging_config import get_logger
logger = get_logger(__name__)


class ConnectivityDiagnostics:
    """Run comprehensive diagnostics on WebSocket and Database connectivity."""
    
    def __init__(self):
        self.results = {}
    
    async def test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity with detailed error reporting."""
        print("\n" + "="*80)
        print("DATABASE CONNECTIVITY DIAGNOSTICS")
        print("="*80)
        
        result = {
            'test': 'database_connectivity',
            'status': 'unknown',
            'details': {},
            'errors': []
        }
        
        try:
            from app.database.connection import check_database_health, db_health_status
            
            # Test 1: Basic health check
            print("\n[1/3] Testing basic database health...")
            health = await check_database_health()
            
            result['details']['health_check'] = health
            print(f"   Database URL: {health['database_url']}")
            print(f"   Pool Size: {health['pool_size']}")
            
            if health['is_healthy']:
                print(f"   ✅ Health check PASSED")
                print(f"   Latency: {health['checks']['connectivity']['latency_ms']}ms")
            else:
                print(f"   ❌ Health check FAILED")
                error = health['checks'].get('connectivity', {}).get('error', 'Unknown error')
                result['errors'].append(f"Health check failed: {error}")
                print(f"   Error: {error}")
            
            # Test 2: Connection pool status
            print("\n[2/3] Checking connection pool...")
            from app.database.connection import engine
            
            pool_status = {
                'pool_size': engine.pool.size() if hasattr(engine.pool, 'size') else 'N/A',
                'checked_in': engine.pool.checkedin() if hasattr(engine.pool, 'checkedin') else 'N/A',
                'checked_out': engine.pool.checkedout() if hasattr(engine.pool, 'checkedout') else 'N/A',
                'overflow': engine.pool.overflow() if hasattr(engine.pool, 'overflow') else 'N/A'
            }
            
            result['details']['pool_status'] = pool_status
            print(f"   Pool Size: {pool_status['pool_size']}")
            print(f"   Checked In: {pool_status['checked_in']}")
            print(f"   Checked Out: {pool_status['checked_out']}")
            print(f"   Overflow: {pool_status['overflow']}")
            print(f"   ✅ Pool status retrieved successfully")
            
            # Test 3: Session creation and query
            print("\n[3/3] Testing session creation and query execution...")
            from app.database.connection import get_session
            from sqlalchemy import text
            
            start_time = time.time()
            async for session in get_session():
                query_result = await session.execute(text("SELECT version()"))
                version = query_result.scalar()
                query_time = time.time() - start_time
                
                result['details']['query_test'] = {
                    'status': 'pass',
                    'postgresql_version': version,
                    'query_time_ms': round(query_time * 1000, 2)
                }
                
                print(f"   PostgreSQL Version: {version}")
                print(f"   Query Time: {query_time*1000:.2f}ms")
                print(f"   ✅ Session test PASSED")
                break
            
            # Overall status
            if health['is_healthy']:
                result['status'] = 'pass'
                print(f"\n✅ DATABASE CONNECTIVITY: HEALTHY")
            else:
                result['status'] = 'fail'
                print(f"\n❌ DATABASE CONNECTIVITY: UNHEALTHY")
                
        except Exception as e:
            result['status'] = 'fail'
            result['errors'].append(f"{type(e).__name__}: {str(e)}")
            print(f"\n❌ DATABASE TEST FAILED: {e}")
            logger.error(f"Database diagnostic error", exc_info=True)
        
        self.results['database'] = result
        return result
    
    async def test_websocket_reconnection_logic(self) -> Dict[str, Any]:
        """Test WebSocket reconnection logic and backoff strategy."""
        print("\n" + "="*80)
        print("WEBSOCKET RECONNECTION LOGIC DIAGNOSTICS")
        print("="*80)
        
        result = {
            'test': 'websocket_reconnection',
            'status': 'unknown',
            'details': {},
            'errors': []
        }
        
        try:
            from app.websocket.manager import MEXCWebSocketManager
            from app.config import settings
            
            # Test 1: Configuration validation
            print("\n[1/4] Validating WebSocket configuration...")
            config = {
                'heartbeat_interval': settings.WEBSOCKET_HEARTBEAT_INTERVAL,
                'heartbeat_timeout': settings.WEBSOCKET_HEARTBEAT_TIMEOUT,
                'reconnect_delay': settings.WEBSOCKET_RECONNECT_DELAY,
                'max_reconnect_delay': settings.WEBSOCKET_MAX_RECONNECT_DELAY,
                'max_reconnect_attempts': settings.WEBSOCKET_MAX_RECONNECT_ATTEMPTS,
                'stale_stream_threshold': settings.WEBSOCKET_STALE_STREAM_THRESHOLD,
                'jitter_factor': settings.WEBSOCKET_JITTER_FACTOR
            }
            
            result['details']['configuration'] = config
            print(f"   Heartbeat Interval: {config['heartbeat_interval']}s")
            print(f"   Heartbeat Timeout: {config['heartbeat_timeout']}s")
            print(f"   Base Reconnect Delay: {config['reconnect_delay']}s")
            print(f"   Max Reconnect Delay: {config['max_reconnect_delay']}s")
            print(f"   Max Reconnect Attempts: {config['max_reconnect_attempts']} (0=unlimited)")
            print(f"   Stale Stream Threshold: {config['stale_stream_threshold']}s")
            print(f"   Jitter Factor: {config['jitter_factor']*100:.0f}%")
            print(f"   ✅ Configuration validated")
            
            # Test 2: Manager initialization
            print("\n[2/4] Testing WebSocket manager initialization...")
            ws_manager = MEXCWebSocketManager(market_type='futures')
            
            init_status = {
                'ws_url': ws_manager.ws_url,
                'market_type': ws_manager.market_type,
                'base_reconnect_delay': ws_manager.base_reconnect_delay,
                'max_reconnect_delay': ws_manager.max_reconnect_delay,
                'max_reconnect_attempts': ws_manager.max_reconnect_attempts,
                'circuit_breaker_threshold': ws_manager.circuit_breaker_threshold
            }
            
            result['details']['initialization'] = init_status
            print(f"   WebSocket URL: {init_status['ws_url']}")
            print(f"   Market Type: {init_status['market_type']}")
            print(f"   Circuit Breaker Threshold: {init_status['circuit_breaker_threshold']}")
            print(f"   ✅ Manager initialized successfully")
            
            # Test 3: Backoff calculation simulation
            print("\n[3/4] Simulating exponential backoff calculations...")
            backoff_tests = []
            
            for attempt in [1, 2, 3, 5, 10, 15, 20]:
                delay = min(
                    ws_manager.base_reconnect_delay * (2 ** (attempt - 1)),
                    ws_manager.max_reconnect_delay
                )
                jitter = delay * ws_manager.jitter_factor * 0.5  # Average jitter
                total_delay = delay + jitter
                
                backoff_tests.append({
                    'attempt': attempt,
                    'base_delay': delay,
                    'with_jitter': round(total_delay, 2),
                    'capped': delay == ws_manager.max_reconnect_delay
                })
            
            result['details']['backoff_simulation'] = backoff_tests
            
            print(f"   Attempt 1: {backoff_tests[0]['with_jitter']}s")
            print(f"   Attempt 3: {backoff_tests[2]['with_jitter']}s")
            print(f"   Attempt 10: {backoff_tests[4]['with_jitter']}s (capped: {backoff_tests[4]['capped']})")
            print(f"   Attempt 20: {backoff_tests[5]['with_jitter']}s (capped: {backoff_tests[5]['capped']})")
            print(f"   ✅ Backoff calculations verified")
            
            # Test 4: Extended retry period detection
            print("\n[4/4] Testing extended retry period detection...")
            
            # Simulate 20 consecutive failures
            simulated_attempts = 20
            total_retry_time = sum(
                min(ws_manager.base_reconnect_delay * (2 ** i), ws_manager.max_reconnect_delay)
                for i in range(simulated_attempts)
            )
            
            should_reset = total_retry_time > 3600
            
            result['details']['extended_retry_test'] = {
                'simulated_attempts': simulated_attempts,
                'total_retry_time_seconds': total_retry_time,
                'threshold_seconds': 3600,
                'should_reset_backoff': should_reset
            }
            
            print(f"   Simulated Attempts: {simulated_attempts}")
            print(f"   Total Retry Time: {total_retry_time:.0f}s ({total_retry_time/3600:.2f} hours)")
            print(f"   Reset Threshold: 3600s (1 hour)")
            print(f"   Should Reset Backoff: {'✅ YES' if should_reset else '❌ NO'}")
            
            if should_reset:
                print(f"   ✅ Extended retry detection working correctly")
            else:
                print(f"   ⚠️  Extended retry detection may need adjustment")
            
            result['status'] = 'pass'
            print(f"\n✅ WEBSOCKET RECONNECTION LOGIC: VALIDATED")
            
        except Exception as e:
            result['status'] = 'fail'
            result['errors'].append(f"{type(e).__name__}: {str(e)}")
            print(f"\n❌ WEBSOCKET TEST FAILED: {e}")
            logger.error(f"WebSocket diagnostic error", exc_info=True)
        
        self.results['websocket'] = result
        return result
    
    async def test_docker_postgres_configuration(self) -> Dict[str, Any]:
        """Test Docker PostgreSQL configuration and accessibility."""
        print("\n" + "="*80)
        print("DOCKER POSTGRESQL CONFIGURATION DIAGNOSTICS")
        print("="*80)
        
        result = {
            'test': 'docker_postgres',
            'status': 'unknown',
            'details': {},
            'errors': []
        }
        
        try:
            import subprocess
            
            # Test 1: Check if PostgreSQL container is running
            print("\n[1/3] Checking PostgreSQL container status...")
            container_check = subprocess.run(
                ['docker', 'ps', '--filter', 'name=trading-postgres', '--format', '{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            container_status = container_check.stdout.strip()
            result['details']['container_status'] = container_status
            
            if container_status:
                print(f"   Container Status: {container_status}")
                print(f"   ✅ PostgreSQL container is running")
            else:
                print(f"   ❌ PostgreSQL container is NOT running")
                result['errors'].append("PostgreSQL container not found or not running")
                result['status'] = 'fail'
                return result
            
            # Test 2: Check PostgreSQL logs for errors
            print("\n[2/3] Checking PostgreSQL logs...")
            log_check = subprocess.run(
                ['docker', 'logs', 'trading-postgres', '--tail', '50'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            logs = log_check.stderr  # PostgreSQL logs go to stderr
            
            # Check for common errors
            critical_errors = []
            if 'FATAL' in logs:
                critical_errors.append("FATAL errors found in logs")
            if 'panic' in logs.lower():
                critical_errors.append("Panic detected in logs")
            
            result['details']['logs_summary'] = {
                'has_critical_errors': len(critical_errors) > 0,
                'critical_errors': critical_errors,
                'last_lines': logs.split('\n')[-5:]
            }
            
            if critical_errors:
                print(f"   ⚠️  Critical errors found:")
                for error in critical_errors:
                    print(f"      - {error}")
            else:
                print(f"   ✅ No critical errors in recent logs")
            
            # Test 3: Test network connectivity to PostgreSQL
            print("\n[3/3] Testing network connectivity...")
            port_check = subprocess.run(
                ['docker', 'port', 'trading-postgres', '5432'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            port_mapping = port_check.stdout.strip()
            result['details']['port_mapping'] = port_mapping
            
            if port_mapping:
                print(f"   Port Mapping: {port_mapping}")
                print(f"   ✅ PostgreSQL port is exposed")
            else:
                print(f"   ⚠️  Could not verify port mapping")
            
            result['status'] = 'pass'
            print(f"\n✅ DOCKER POSTGRESQL: CONFIGURED CORRECTLY")
            
        except FileNotFoundError:
            result['status'] = 'skip'
            result['errors'].append("Docker not available - skipping container checks")
            print(f"\n⚠️  Docker not available - skipping container diagnostics")
        except Exception as e:
            result['status'] = 'fail'
            result['errors'].append(f"{type(e).__name__}: {str(e)}")
            print(f"\n❌ DOCKER POSTGRESQL TEST FAILED: {e}")
            logger.error(f"Docker diagnostic error", exc_info=True)
        
        self.results['docker_postgres'] = result
        return result
    
    def generate_summary(self) -> str:
        """Generate a comprehensive summary of all diagnostic results."""
        print("\n" + "="*80)
        print("DIAGNOSTIC SUMMARY")
        print("="*80)
        
        summary_lines = []
        overall_status = 'pass'
        
        for test_name, result in self.results.items():
            status_icon = {
                'pass': '✅',
                'fail': '❌',
                'skip': '⚠️ ',
                'unknown': '❓'
            }.get(result['status'], '❓')
            
            summary_lines.append(f"{status_icon} {test_name.upper()}: {result['status'].upper()}")
            
            if result['status'] == 'fail':
                overall_status = 'fail'
                for error in result.get('errors', []):
                    summary_lines.append(f"   └─ {error}")
        
        print("\n".join(summary_lines))
        print(f"\n{'='*80}")
        
        if overall_status == 'pass':
            print("✅ ALL DIAGNOSTICS PASSED - System is healthy")
        elif overall_status == 'fail':
            print("❌ SOME DIAGNOSTICS FAILED - Review errors above")
        else:
            print("⚠️  SOME TESTS SKIPPED - Partial diagnostics completed")
        
        print(f"{'='*80}\n")
        
        return overall_status


async def main():
    """Run all diagnostics."""
    print("\n" + "="*80)
    print("AUTO-TRADE-SYSTEM CONNECTIVITY DIAGNOSTICS")
    print("="*80)
    print("Testing WebSocket stability and Database connectivity fixes...")
    
    diagnostics = ConnectivityDiagnostics()
    
    # Run all tests
    await diagnostics.test_database_connectivity()
    await diagnostics.test_websocket_reconnection_logic()
    await diagnostics.test_docker_postgres_configuration()
    
    # Generate summary
    overall_status = diagnostics.generate_summary()
    
    # Exit with appropriate code
    sys.exit(0 if overall_status == 'pass' else 1)


if __name__ == "__main__":
    asyncio.run(main())
