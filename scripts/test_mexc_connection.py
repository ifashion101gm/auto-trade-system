#!/usr/bin/env python3
"""Quick test for MEXC connection and position check."""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infra.mexc_client import MEXCClient
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

async def test_mexc():
    """Test MEXC connection and check positions."""
    logger.info("Testing MEXC connection...")
    
    client = None
    try:
        # Initialize MEXC client
        client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        
        # Fetch balance
        logger.info("\nFetching balance...")
        balance = await client.fetch_balance()
        logger.info(f"Balance: {balance}")
        
        # Fetch positions
        logger.info("\nFetching positions...")
        positions = await client.fetch_open_positions()
        logger.info(f"Found {len(positions)} open position(s)")
        
        for pos in positions:
            logger.info(f"  - Symbol: {pos['symbol']}, Side: {pos['side']}, Size: {pos['size']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    result = asyncio.run(test_mexc())
    sys.exit(0 if result else 1)
