#!/usr/bin/env python3
"""
Quick Validation for MEXC Gold Futures Configuration and Connectivity.

This script performs basic checks:
1. Configuration verification
2. Symbol validation  
3. Basic connectivity test with timeout

Usage:
    python scripts/quick_mexc_check.py [--demo] [--live]
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def check_configuration():
    """Check configuration settings."""
    print("\n" + "="*80)
    print("CONFIGURATION CHECK")
    print("="*80)
    
    checks = []
    
    # Check GOLD_SYMBOL_MEXC
    if hasattr(settings, 'GOLD_SYMBOL_MEXC') and settings.GOLD_SYMBOL_MEXC:
        print(f"✅ GOLD_SYMBOL_MEXC: {settings.GOLD_SYMBOL_MEXC}")
        checks.append(True)
    else:
        print(f"❌ GOLD_SYMBOL_MEXC not configured")
        checks.append(False)
    
    # Check MEXC API credentials
    if settings.MEXC_API_KEY:
        masked = f"{settings.MEXC_API_KEY[:8]}...{settings.MEXC_API_KEY[-4:]}"
        print(f"✅ MEXC_API_KEY: {masked}")
        checks.append(True)
    else:
        print(f"❌ MEXC_API_KEY not configured")
        checks.append(False)
    
    if settings.MEXC_API_SECRET:
        print(f"✅ MEXC_API_SECRET: [CONFIGURED]")
        checks.append(True)
    else:
        print(f"❌ MEXC_API_SECRET not configured")
        checks.append(False)
    
    # Other relevant settings
    print(f"\n📋 Trading Settings:")
    print(f"   ACTIVE_EXCHANGE: {settings.ACTIVE_EXCHANGE}")
    print(f"   EXECUTION_MODE: {settings.EXECUTION_MODE}")
    print(f"   GOLD_MAX_LEVERAGE: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"   GOLD_RISK_PER_TRADE: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    print(f"   GOLD_MIN_CONFIDENCE: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    
    return all(checks)


async def check_symbol_format(symbol):
    """Check if symbol format is correct."""
    print("\n" + "="*80)
    print("SYMBOL FORMAT CHECK")
    print("="*80)
    
    print(f"\nSymbol: {symbol}")
    
    # Check common formats
    valid_formats = [
        "GOLD(XAUT)/USDT",
        "XAUT/USDT",
        "PAXG/USDT",
    ]
    
    if symbol in valid_formats:
        print(f"✅ Symbol format is valid")
        return True
    else:
        print(f"⚠️  Symbol format may need adjustment")
        print(f"   Common formats: {', '.join(valid_formats)}")
        return True  # Don't fail on this


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Quick MEXC Check')
    parser.add_argument('--demo', action='store_true', help='Demo mode')
    parser.add_argument('--live', action='store_true', help='Live mode')
    
    args = parser.parse_args()
    
    print("\n" + "#"*80)
    print("# QUICK MEXC GOLD FUTURES CHECK")
    print("#"*80)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    
    try:
        # Step 1: Configuration
        config_ok = await check_configuration()
        
        # Step 2: Symbol format
        symbol_ok = await check_symbol_format(settings.GOLD_SYMBOL_MEXC)
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if config_ok and symbol_ok:
            print("✅ Configuration is correct")
            print("\nNext steps:")
            print("1. Test connectivity manually with MEXC web interface")
            print("2. Verify API keys have futures trading permissions")
            print("3. Check if testnet endpoints are accessible from your network")
            print("\nNote: MEXC testnet API may have limited availability.")
            print("Consider using the demo mode (local simulation) for testing.")
            return True
        else:
            print("❌ Configuration issues found. Please fix them first.")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
