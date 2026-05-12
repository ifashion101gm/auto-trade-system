#!/usr/bin/env python3
"""
Production Monitoring Queries - Example queries for new production tables.
Demonstrates how to query risk violations, recovery reviews, and execution logs.

Usage:
    python scripts/production_monitoring_queries.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.repositories import (
    RiskEventRepository,
    RecoveryEventRepository,
    ExecutionLogRepository,
    TradeRepository
)
from app.database.connection import get_session
from app.logging_config import get_logger

logger = get_logger(__name__)


async def query_recent_risk_violations(hours: int = 24):
    """
    Get recent risk violations from the last N hours.
    
    Args:
        hours: Number of hours to look back (default: 24)
    """
    print("\n" + "="*70)
    print(f"RISK VIOLATIONS (Last {hours} Hours)")
    print("="*70)
    
    async for db_session in get_session():
        try:
            risk_repo = RiskEventRepository()
            violations = await risk_repo.get_recent_violations(db_session, hours=hours)
            
            if not violations:
                print("✅ No risk violations detected")
                return
            
            print(f"\nFound {len(violations)} violation(s):\n")
            
            for i, violation in enumerate(violations, 1):
                print(f"{i}. [{violation.risk_level}] {violation.event_type}")
                print(f"   Trade ID: {violation.trade_id or 'N/A'}")
                print(f"   Description: {violation.description}")
                print(f"   Action Taken: {violation.action_taken or 'None'}")
                print(f"   Timestamp: {violation.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                
                if violation.metrics_json:
                    import json
                    metrics = json.loads(violation.metrics_json)
                    print(f"   Metrics: {metrics}")
                
                print()
                
        except Exception as e:
            logger.error(f"Failed to query risk violations: {e}")
        finally:
            await db_session.close()


async def query_pending_manual_reviews():
    """Get all recovery events requiring manual review."""
    print("\n" + "="*70)
    print("PENDING MANUAL REVIEWS")
    print("="*70)
    
    async for db_session in get_session():
        try:
            recovery_repo = RecoveryEventRepository()
            reviews = await recovery_repo.get_pending_reviews(db_session)
            
            if not reviews:
                print("✅ No pending manual reviews")
                return
            
            print(f"\nFound {len(reviews)} review(s) requiring attention:\n")
            
            for i, review in enumerate(reviews, 1):
                print(f"{i}. [{review.recovery_type}] {review.symbol}")
                print(f"   Exchange: {review.exchange.upper()}")
                print(f"   Trade ID: {review.trade_id or 'N/A'}")
                print(f"   Description: {review.description}")
                print(f"   Auto-Repaired: {'Yes' if review.auto_repaired else 'No'}")
                print(f"   Timestamp: {review.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                
                if review.old_state:
                    import json
                    old_state = json.loads(review.old_state)
                    print(f"   Old State: {old_state}")
                
                if review.new_state:
                    import json
                    new_state = json.loads(review.new_state)
                    print(f"   New State: {new_state}")
                
                print()
                
        except Exception as e:
            logger.error(f"Failed to query pending reviews: {e}")
        finally:
            await db_session.close()


async def query_execution_logs_for_trade(trade_id: str):
    """
    Get all execution logs for a specific trade.
    
    Args:
        trade_id: The trade ID to query logs for
    """
    print("\n" + "="*70)
    print(f"EXECUTION LOGS FOR TRADE: {trade_id}")
    print("="*70)
    
    async for db_session in get_session():
        try:
            exec_log_repo = ExecutionLogRepository()
            logs = await exec_log_repo.get_logs_by_trade(trade_id, db_session)
            
            if not logs:
                print(f"⚠️  No execution logs found for trade {trade_id}")
                return
            
            print(f"\nFound {len(logs)} log entry(s):\n")
            
            for i, log in enumerate(logs, 1):
                status_emoji = "✅" if log.status == "SUCCESS" else "❌" if log.status == "FAILED" else "🔄"
                
                print(f"{i}. {status_emoji} [{log.status}] {log.action}")
                print(f"   Exchange: {log.exchange.upper()}")
                print(f"   Symbol: {log.symbol}")
                print(f"   Order ID: {log.order_id or 'N/A'}")
                print(f"   Latency: {log.latency_ms:.2f}ms" if log.latency_ms else "   Latency: N/A")
                print(f"   Retries: {log.retry_count}")
                print(f"   Timestamp: {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                
                if log.error_message:
                    print(f"   Error: {log.error_message}")
                
                if log.request_payload:
                    import json
                    try:
                        request = json.loads(log.request_payload)
                        print(f"   Request: {request}")
                    except:
                        pass
                
                if log.response_payload:
                    import json
                    try:
                        response = json.loads(log.response_payload)
                        print(f"   Response: {response}")
                    except:
                        pass
                
                print()
                
        except Exception as e:
            logger.error(f"Failed to query execution logs: {e}")
        finally:
            await db_session.close()


async def query_recent_order_state_changes(limit: int = 10):
    """
    Query recent ORDER_STATE_CHANGED events from event store.
    
    Args:
        limit: Maximum number of events to retrieve (default: 10)
    """
    print("\n" + "="*70)
    print(f"RECENT ORDER STATE CHANGES (Last {limit})")
    print("="*70)
    
    from app.events.event_store import event_store
    
    async for db_session in get_session():
        try:
            events = await event_store.get_recent_events(
                db_session,
                event_type='ORDER_STATE_CHANGED',
                limit=limit
            )
            
            if not events:
                print("✅ No recent order state changes")
                return
            
            print(f"\nFound {len(events)} state change(s):\n")
            
            for i, event in enumerate(events, 1):
                payload = event['payload']
                from_state = payload.get('from_state', 'N/A')
                to_state = payload.get('to_state', 'N/A')
                
                # Determine if critical transition
                critical_states = ['REJECTED', 'CANCELED', 'EXPIRED', 'RECOVERY_REQUIRED']
                is_critical = to_state in critical_states
                emoji = "🚨" if is_critical else "ℹ️"
                
                print(f"{i}. {emoji} {from_state.upper()} → {to_state.upper()}")
                print(f"   Trade ID: {event.get('trade_id', 'N/A')}")
                print(f"   Order ID: {payload.get('order_id', 'N/A')}")
                print(f"   Symbol: {payload.get('symbol', 'N/A')}")
                print(f"   Timestamp: {event['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
        except Exception as e:
            logger.error(f"Failed to query order state changes: {e}")
        finally:
            await db_session.close()


async def query_risk_violation_summary(days: int = 7):
    """
    Get summary of risk violations over the past N days.
    
    Args:
        days: Number of days to analyze (default: 7)
    """
    print("\n" + "="*70)
    print(f"RISK VIOLATION SUMMARY (Last {days} Days)")
    print("="*70)
    
    from sqlalchemy import select, func
    from app.database.models import RiskEvents
    
    async for db_session in get_session():
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Count by type
            type_query = select(
                RiskEvents.event_type,
                func.count(RiskEvents.id).label('count')
            ).where(
                (RiskEvents.timestamp >= cutoff) &
                (RiskEvents.risk_level.in_(['HIGH', 'CRITICAL']))
            ).group_by(
                RiskEvents.event_type
            ).order_by(
                func.count(RiskEvents.id).desc()
            )
            
            result = await db_session.execute(type_query)
            type_counts = result.all()
            
            if not type_counts:
                print("✅ No high/critical risk violations in this period")
                return
            
            print(f"\nViolation Counts by Type:\n")
            total = 0
            for event_type, count in type_counts:
                print(f"• {event_type}: {count}")
                total += count
            
            print(f"\nTotal High/Critical Violations: {total}")
            
            # Count by risk level
            level_query = select(
                RiskEvents.risk_level,
                func.count(RiskEvents.id).label('count')
            ).where(
                RiskEvents.timestamp >= cutoff
            ).group_by(
                RiskEvents.risk_level
            ).order_by(
                func.count(RiskEvents.id).desc()
            )
            
            result = await db_session.execute(level_query)
            level_counts = result.all()
            
            print(f"\nViolations by Risk Level:\n")
            for level, count in level_counts:
                emoji = "🚨" if level == "CRITICAL" else "🔴" if level == "HIGH" else "🟡"
                print(f"{emoji} {level}: {count}")
            
            print()
                
        except Exception as e:
            logger.error(f"Failed to query risk violation summary: {e}")
        finally:
            await db_session.close()


async def main():
    """Run all production monitoring queries."""
    print("\n" + "="*70)
    print("PRODUCTION MONITORING QUERIES")
    print("="*70)
    print(f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    try:
        # 1. Recent risk violations (last 24 hours)
        await query_recent_risk_violations(hours=24)
        
        # 2. Pending manual reviews
        await query_pending_manual_reviews()
        
        # 3. Recent order state changes
        await query_recent_order_state_changes(limit=10)
        
        # 4. Risk violation summary (last 7 days)
        await query_risk_violation_summary(days=7)
        
        # 5. Example: Query execution logs for a specific trade
        # Uncomment and replace with actual trade ID to test:
        # await query_execution_logs_for_trade("your-trade-id-here")
        
        print("\n" + "="*70)
        print("✅ All monitoring queries completed successfully")
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Monitoring queries failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
