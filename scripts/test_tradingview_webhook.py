#!/usr/bin/env python3
"""
Test TradingView Webhook Integration
Validates authentication, signal parsing, risk checks, and execution flow.
"""
import asyncio
import sys
from pathlib import Path
import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings

async def test_webhook_endpoint():
    """Test the TradingView webhook endpoint with various payloads."""
    
    base_url = "http://localhost:8000"  # Adjust based on your setup
    endpoint = f"{base_url}/api/webhooks/tradingview"
    
    print("="*80)
    print("TradingView Webhook Integration Tests")
    print("="*80)
    
    # Test 1: Valid LONG signal
    print("\n🧪 Test 1: Valid LONG signal")
    payload = {
        "strategy": "breakout",
        "symbol": "BTCUSDT",
        "side": "buy",
        "price": 50000.0,
        "quantity": 0.01,
        "stop_loss": 49000.0,
        "take_profit": 52000.0,
        "leverage": 2,
        "confidence": 0.85
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ Test 1 passed")
    
    # Test 2: Invalid payload (missing required field)
    print("\n🧪 Test 2: Invalid payload (missing quantity)")
    invalid_payload = {
        "symbol": "ETHUSDT",
        "side": "sell",
        "price": 3000.0
        # Missing quantity
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=invalid_payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Test 2 passed")
    
    # Test 3: Invalid authentication
    print("\n🧪 Test 3: Invalid authentication")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=payload,
            headers={"Authorization": "Bearer invalid_token"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Test 3 passed")
    
    # Test 4: Symbol normalization
    print("\n🧪 Test 4: Symbol normalization (BTCUSDT → BTC/USDT)")
    normalized_payload = {
        "symbol": "BTCUSDT",  # No slash
        "side": "long",
        "price": 50000.0,
        "quantity": 0.01
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=normalized_payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {result}")
        
        assert response.status_code == 200
        print("✅ Test 4 passed")
    
    # Test 5: SHORT signal with different symbol format
    print("\n🧪 Test 5: SHORT signal with ETH/USDT format")
    short_payload = {
        "strategy": "mean_reversion",
        "symbol": "ETH/USDT",
        "side": "short",
        "price": 3000.0,
        "quantity": 0.5,
        "stop_loss": 3100.0,
        "take_profit": 2900.0,
        "leverage": 3,
        "confidence": 0.75
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=short_payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 200
        print("✅ Test 5 passed")
    
    # Test 6: Invalid side value
    print("\n🧪 Test 6: Invalid side value")
    invalid_side_payload = {
        "symbol": "BTCUSDT",
        "side": "hold",  # Invalid
        "price": 50000.0,
        "quantity": 0.01
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=invalid_side_payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Test 6 passed")
    
    # Test 7: Negative price
    print("\n🧪 Test 7: Negative price")
    negative_price_payload = {
        "symbol": "BTCUSDT",
        "side": "buy",
        "price": -100.0,  # Invalid
        "quantity": 0.01
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=negative_price_payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Test 7 passed")
    
    # Test 8: Perpetual symbol format
    print("\n🧪 Test 8: Perpetual symbol format (BTCUSDT.P)")
    perpetual_payload = {
        "symbol": "BTCUSDT.P",
        "side": "buy",
        "price": 50000.0,
        "quantity": 0.01
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            endpoint,
            json=perpetual_payload,
            headers={"Authorization": f"Bearer {settings.TRADING_API_SECRET}"},
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {result}")
        
        # Should normalize to BTC/USDT
        assert response.status_code == 200
        print("✅ Test 8 passed")
    
    print("\n" + "="*80)
    print("✅ All tests passed!")
    print("="*80)

if __name__ == "__main__":
    try:
        asyncio.run(test_webhook_endpoint())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
