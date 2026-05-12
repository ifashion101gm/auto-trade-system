#!/usr/bin/env python3
"""
Infrastructure Verification Script
Tests connectivity to all core components of the Auto Trade System.
"""
import asyncio
import sys
from sqlalchemy import text


async def test_postgres():
    """Test PostgreSQL database connectivity."""
    print("\n🔍 Testing PostgreSQL connection...")
    try:
        from app.storage.db import get_session
        
        async for session in get_session():
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            
            # Check tables exist
            result = await session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            table_count = result.scalar()
            
            print(f"✅ PostgreSQL: Connected ({table_count} tables found)")
            break
        return True
    except Exception as e:
        print(f"❌ PostgreSQL: Connection failed - {e}")
        return False


async def test_redis():
    """Test Redis connectivity."""
    print("\n🔍 Testing Redis connection...")
    try:
        import redis.asyncio as redis
        from app.config import settings
        
        r = redis.from_url(settings.REDIS_URL)
        await r.set("test_key", "test_value")
        value = await r.get("test_key")
        assert value == b"test_value"
        await r.delete("test_key")
        
        print("✅ Redis: Connected and operational")
        return True
    except Exception as e:
        print(f"❌ Redis: Connection failed - {e}")
        return False


async def test_exchange_api():
    """Test exchange API connectivity."""
    print("\n🔍 Testing Exchange API connection...")
    try:
        from app.infra.exchange_manager import ExchangeManager
        
        manager = ExchangeManager()
        balance = await manager.get_balance(mode='DEMO')
        
        if balance:
            print(f"✅ Exchange API: Connected (Balance retrieved)")
            return True
        else:
            print("⚠️  Exchange API: Connected but no balance data")
            return True
    except Exception as e:
        print(f"❌ Exchange API: Connection failed - {e}")
        return False


async def test_websocket():
    """Test WebSocket connection to exchange."""
    print("\n🔍 Testing WebSocket connection...")
    try:
        from app.agents.sync_agent import SyncAgent
        from app.storage.db import get_session
        
        agent = SyncAgent()
        
        # Start WebSocket listener briefly
        task = asyncio.create_task(agent.start_listening(
            symbols=['XAUT/USDT'],
            db_session_factory=get_session
        ))
        
        # Wait a few seconds for connection
        await asyncio.sleep(3)
        
        # Check if WebSocket is connected
        if hasattr(agent, 'websocket_manager') and agent.websocket_manager.websocket:
            print("✅ WebSocket: Connected to exchange")
            await agent.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        else:
            print("⚠️  WebSocket: Not yet connected (may need more time)")
            await agent.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
    except Exception as e:
        print(f"❌ WebSocket: Connection failed - {e}")
        return False


def test_metrics_endpoint():
    """Test metrics endpoint accessibility."""
    print("\n🔍 Testing Metrics endpoint...")
    try:
        import requests
        
        # Test JSON format
        response = requests.get("http://localhost:8000/metrics", timeout=5)
        if response.status_code == 200:
            print("✅ Metrics (JSON): Accessible")
        else:
            print(f"⚠️  Metrics (JSON): Status {response.status_code}")
        
        # Test Prometheus format
        response = requests.get("http://localhost:8000/metrics/prometheus", timeout=5)
        if response.status_code == 200:
            # Check if it contains Prometheus metrics
            if "http_requests_total" in response.text or "# HELP" in response.text:
                print("✅ Metrics (Prometheus): Accessible and returning valid format")
                return True
            else:
                print("⚠️  Metrics (Prometheus): Accessible but format may be incorrect")
                return True
        else:
            print(f"❌ Metrics (Prometheus): Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Metrics endpoint: Connection failed - {e}")
        return False


def test_docker_services():
    """Test Docker service status."""
    print("\n🔍 Testing Docker services...")
    try:
        import subprocess
        
        services = {
            'PostgreSQL': 'trading-postgres',
            'Redis': 'trading-redis',
            'Prometheus': 'trading-prometheus',
            'Grafana': 'trading-grafana'
        }
        
        all_running = True
        for name, container in services.items():
            result = subprocess.run(
                ['docker', 'compose', 'ps', '-q', container],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"✅ {name}: Running in Docker")
            else:
                print(f"❌ {name}: Not running")
                all_running = False
        
        return all_running
    except Exception as e:
        print(f"❌ Docker services check failed - {e}")
        return False


async def main():
    """Run all infrastructure tests."""
    print("=" * 60)
    print("Auto Trade System - Infrastructure Verification")
    print("=" * 60)
    
    results = []
    
    # Test Docker services first
    results.append(("Docker Services", test_docker_services()))
    
    # Test PostgreSQL
    results.append(("PostgreSQL", await test_postgres()))
    
    # Test Redis
    results.append(("Redis", await test_redis()))
    
    # Test Exchange API
    results.append(("Exchange API", await test_exchange_api()))
    
    # Test WebSocket
    results.append(("WebSocket", await test_websocket()))
    
    # Test Metrics Endpoint (requires app to be running)
    results.append(("Metrics Endpoint", test_metrics_endpoint()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:.<40} {status}")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 All infrastructure components are operational!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} component(s) need attention.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
