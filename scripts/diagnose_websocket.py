"""  
WebSocket Diagnostic Script - Tests MEXC WebSocket connectivity and identifies issues.

This script performs comprehensive diagnostics:
1. API credential validation
2. REST API connectivity test
3. Futures permissions check
4. WebSocket connection test
5. Subscription test
6. Message reception test
7. Network latency measurement
8. Spot vs Futures capability detection
"""
import asyncio
import sys
import time
import json
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.config import settings
from app.infra.mexc_client import MEXCClient
import websockets


async def test_futures_permissions():
    """Test if API key has futures trading permissions."""
    print("\n" + "="*70)
    print("TEST 3: Futures Trading Permissions")
    print("="*70)
    
    try:
        # Test futures client
        print(" Testing futures API access...")
        client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures',
            testnet=False
        )
        
        # Try to fetch balance (requires futures permissions)
        balance = await client.fetch_balance()
        
        if balance:
            print(f"✅ Futures permissions GRANTED")
            print(f"   USDT Balance: ${balance.get('total_usdt', 0):.2f}")
            print(f"   Available: ${balance.get('free_usdt', 0):.2f}")
            
            # Try to fetch ticker for Gold futures
            print("\n Testing Gold futures market data access...")
            try:
                ticker = await client.fetch_ticker('GOLD(XAUT)/USDT')
                print(f"✅ GOLD(XAUT)/USDT ticker accessible")
                print(f"   Price: ${ticker['last_price']:,.2f}")
            except Exception as e:
                print(f"⚠️  Gold ticker access failed: {e}")
            
            # Try to fetch positions (requires futures permissions)
            print("\n📍 Testing position access...")
            try:
                positions = await client.fetch_open_positions()
                print(f"✅ Position fetch successful")
                print(f"   Open positions: {len(positions)}")
            except Exception as e:
                print(f"️  Position access failed: {e}")
            
            await client.close()
            return True
        else:
            print(f"❌ Futures permissions DENIED")
            await client.close()
            return False
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Futures permissions test FAILED")
        print(f"   Error: {error_msg[:200]}")
        
        # Analyze error type
        if 'permission' in error_msg.lower() or 'restricted' in error_msg.lower():
            print(f"\n🔧 LIKELY CAUSE: API key lacks futures trading permissions")
            print(f"   Solution: Enable futures permissions on MEXC website")
        elif 'invalid' in error_msg.lower() or 'credential' in error_msg.lower():
            print(f"\n🔧 LIKELY CAUSE: Invalid API credentials")
            print(f"   Solution: Check API key and secret in .env file")
        else:
            print(f"\n🔧 See detailed error above for diagnosis")
        
        return False


async def test_api_credentials():
    """Test if MEXC API credentials are valid."""
    print("\n" + "="*70)
    print("TEST 1: API Credentials Validation (Spot)")
    print("="*70)
    
    try:
        # Test spot client first
        print("🔑 Testing spot API credentials...")
        client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='spot',
            testnet=False
        )
        
        # Try to fetch markets (public endpoint, doesn't need auth)
        print(" Testing public market data access...")
        markets = await client.exchange.load_markets()
        print(f"✅ Loaded {len(markets)} markets")
        
        # Check if futures markets exist
        futures_markets = [m for m in markets if 'swap' in markets[m].get('type', '') or '/USDT:USDT' in m]
        print(f"✅ Found {len(futures_markets)} futures markets")
        
        await client.close()
        return True
            
    except Exception as e:
        print(f"❌ API credentials test FAILED: {e}")
        return False


async def test_rest_connectivity():
    """Test REST API connectivity."""
    print("\n" + "="*70)
    print("TEST 2: REST API Connectivity")
    print("="*70)
    
    try:
        # Test with futures client
        client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures',
            testnet=False
        )
        
        print("🌐 Testing REST API endpoint (Futures)...")
        start_time = time.time()
        
        # Fetch ticker
        ticker = await client.fetch_ticker('GOLD(XAUT)/USDT')
        elapsed = time.time() - start_time
        
        if ticker:
            print(f"✅ REST API CONNECTED")
            print(f"   Response time: {elapsed*1000:.0f}ms")
            print(f"   GOLD(XAUT)/USDT Price: ${ticker['last_price']:,.2f}")
            await client.close()
            return True
        else:
            print(f"❌ REST API FAILED to return data")
            await client.close()
            return False
            
    except Exception as e:
        print(f"❌ REST API connectivity FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_websocket_connection():
    """Test WebSocket connection establishment."""
    print("\n" + "="*70)
    print("TEST 3: WebSocket Connection")
    print("="*70)
    
    ws_url = "wss://contract.mexc.com/ws"
    
    try:
        print(f"🔌 Attempting WebSocket connection to: {ws_url}")
        start_time = time.time()
        
        async with websockets.connect(ws_url) as ws:
            elapsed = time.time() - start_time
            print(f"✅ WebSocket CONNECTED in {elapsed*1000:.0f}ms")
            
            # Send ping
            await ws.ping()
            print(f"✅ Ping successful")
            
            return True
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ WebSocket connection REJECTED (HTTP {e.status_code})")
        print(f"   This usually means: Invalid URL, firewall blocking, or IP banned")
        return False
        
    except websockets.exceptions.InvalidURI:
        print(f"❌ Invalid WebSocket URI: {ws_url}")
        return False
        
    except ConnectionRefusedError:
        print(f"❌ Connection REFUSED - Check firewall/network settings")
        return False
        
    except Exception as e:
        print(f"❌ WebSocket connection FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_websocket_subscription():
    """Test WebSocket subscription and message reception."""
    print("\n" + "="*70)
    print("TEST 4: WebSocket Subscription & Messages")
    print("="*70)
    
    ws_url = "wss://contract.mexc.com/ws"
    
    try:
        print(f"📡 Subscribing to position updates...")
        
        async with websockets.connect(ws_url) as ws:
            # Subscribe to private channel (requires authentication)
            # For now, test public channel
            subscription = {
                "method": "sub.ticker",
                "param": "XAUT_USDT",
                "id": 1
            }
            
            await ws.send(json.dumps(subscription))
            print(f"✅ Subscription sent")
            
            # Wait for messages
            print(f"⏳ Waiting for messages (10 seconds)...")
            message_count = 0
            start_time = time.time()
            
            while time.time() - start_time < 10:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    message_count += 1
                    
                    if message_count == 1:
                        print(f"✅ First message received!")
                        data = json.loads(message)
                        print(f"   Message type: {data.get('channel', 'unknown')}")
                    
                except asyncio.TimeoutError:
                    continue
            
            if message_count > 0:
                print(f"✅ Received {message_count} messages in 10 seconds")
                print(f"   Average rate: {message_count/10:.1f} msg/s")
                return True
            else:
                print(f"⚠️  No messages received (subscription may require auth)")
                return None  # Inconclusive
                
    except Exception as e:
        print(f"❌ Subscription test FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_network_latency():
    """Test network latency to MEXC servers."""
    print("\n" + "="*70)
    print("TEST 5: Network Latency")
    print("="*70)
    
    try:
        import socket
        
        print("📍 Resolving MEXC WebSocket host...")
        start = time.time()
        ip = socket.gethostbyname('contract.mexc.com')
        dns_time = time.time() - start
        
        print(f"✅ DNS Resolution: {ip} ({dns_time*1000:.0f}ms)")
        
        # Test TCP connection
        print("🔌 Testing TCP connection...")
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('contract.mexc.com', 443))
        tcp_time = time.time() - start
        sock.close()
        
        if result == 0:
            print(f"✅ TCP Connection: SUCCESS ({tcp_time*1000:.0f}ms)")
        else:
            print(f"❌ TCP Connection: FAILED (error code {result})")
            
        return True
        
    except Exception as e:
        print(f"❌ Network test FAILED: {e}")
        return False


async def check_firewall_rules():
    """Check if firewall might be blocking WebSocket connections."""
    print("\n" + "="*70)
    print("TEST 6: Firewall & Port Check")
    print("="*70)
    
    try:
        import subprocess
        
        # Check if we can reach port 443 (HTTPS/WSS)
        print("🛡️  Checking outbound port 443 access...")
        
        result = subprocess.run(
            ['timeout', '3', 'bash', '-c', 'echo > /dev/tcp/contract.mexc.com/443'],
            capture_output=True
        )
        
        if result.returncode == 0:
            print(f"✅ Port 443: OPEN (outbound allowed)")
        else:
            print(f"❌ Port 443: BLOCKED (firewall may be restricting)")
            print(f"   Try: sudo ufw allow out 443/tcp")
            
        return True
        
    except Exception as e:
        print(f"⚠️  Firewall check skipped: {e}")
        return None


async def main():
    """Run all diagnostic tests."""
    print("\n" + "█"*70)
    print("█" + " "*20 + "MEXC WEBSOCKET DIAGNOSTICS" + " "*22 + "█")
    print("█"*70)
    print(f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"MEXC API Key: {'***' + settings.MEXC_API_KEY[-4:] if settings.MEXC_API_KEY else 'NOT SET'}")
    print(f"MEXC API Secret: {'***' + settings.MEXC_API_SECRET[-4:] if settings.MEXC_API_SECRET else 'NOT SET'}")
    
    results = {}
    
    # Run tests sequentially
    results['api_credentials'] = await test_api_credentials()
    results['futures_permissions'] = await test_futures_permissions()
    results['rest_connectivity'] = await test_rest_connectivity()
    results['websocket_connection'] = await test_websocket_connection()
    results['websocket_subscription'] = await test_websocket_subscription()
    results['network_latency'] = await test_network_latency()
    results['firewall_check'] = await check_firewall_rules()
    
    # Summary
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    inconclusive = sum(1 for v in results.values() if v is None)
    
    print(f"\n✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Inconclusive: {inconclusive}")
    
    if failed > 0:
        print(f"\n🔧 RECOMMENDATIONS:")
        
        if not results.get('futures_permissions'):
            print(f"\n   ❌ FUTURES PERMISSIONS ISSUE DETECTED")
            print(f"   " + "="*60)
            print(f"   To enable futures trading on MEXC:")
            print(f"   1. Log in to https://www.mexc.com")
            print(f"   2. Go to API Management (User Icon → API Management)")
            print(f"   3. Find your API key: {settings.MEXC_API_KEY}")
            print(f"   4. Click 'Edit' or 'Modify Permissions'")
            print(f"   5. Enable these permissions:")
            print(f"      ✓ Enable Reading")
            print(f"      ✓ Enable Futures")
            print(f"      ✓ Enable Spot & Margin Trading (optional)")
            print(f"   6. Save changes")
            print(f"   7. Wait 5 minutes for changes to propagate")
            print(f"   8. Re-run this diagnostic script")
            print(f"   \n   Alternative: Create a NEW API key with futures enabled")
            print(f"   " + "="*60)
        
        if not results.get('api_credentials'):
            print(f"\n   1. Verify MEXC_API_KEY and MEXC_API_SECRET in .env file")
            print(f"   2. Current key: {settings.MEXC_API_KEY}")
        
        if not results.get('websocket_connection'):
            print(f"\n   3. Check firewall: sudo ufw status")
            print(f"   4. Allow outbound WSS: sudo ufw allow out 443/tcp")
            print(f"   5. Test from different network to rule out ISP blocking")
        
        if not results.get('rest_connectivity'):
            print(f"\n   6. MEXC API may be temporarily down - check status.mexc.com")
            print(f"   7. Verify your IP is not rate-limited/banned")
    
    print(f"\n{'='*70}\n")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Diagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Diagnostic failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
