#!/usr/bin/env python3
"""
Monitor deployment metrics and alert on threshold violations.
Run this script periodically during the 48-hour validation period.
"""
import asyncio
import httpx
import json
from datetime import datetime
from pathlib import Path

METRICS_URL = "http://localhost:8000/metrics"
LOG_FILE = Path("logs/deployment_monitor.log")

THRESHOLDS = {
    'queue_size': 100,
    'avg_latency_ms': 100,
    'dead_letter_count': 0
}


async def check_metrics():
    """Check system metrics and log results."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(METRICS_URL, timeout=5.0)
            
            if response.status_code != 200:
                log_message(f"[{timestamp}] ❌ Metrics endpoint unavailable: HTTP {response.status_code}")
                return False
            
            metrics = response.json()
            
            # Extract EventBus metrics
            event_bus = metrics.get('event_bus', {})
            queue_size = event_bus.get('queue_size', 0)
            dead_letters = event_bus.get('dead_letter_count', 0)
            processed = event_bus.get('processed_count', 0)
            
            # Extract WebSocket metrics
            websocket = metrics.get('websocket', {})
            connected = websocket.get('connected', False)
            latency = websocket.get('avg_latency_ms', 0)
            uptime = websocket.get('uptime_seconds', 0)
            reconnects = websocket.get('reconnect_count', 0)
            
            # Validate thresholds
            alerts = []
            status_emoji = "✅"
            
            if queue_size >= THRESHOLDS['queue_size']:
                alerts.append(f"⚠️ Queue size high: {queue_size} (threshold: {THRESHOLDS['queue_size']})")
                status_emoji = "⚠️"
            
            if dead_letters > THRESHOLDS['dead_letter_count']:
                alerts.append(f"🚨 Dead letters detected: {dead_letters}")
                status_emoji = "🚨"
            
            if latency >= THRESHOLDS['avg_latency_ms']:
                alerts.append(f"⚠️ High latency: {latency:.0f}ms (threshold: {THRESHOLDS['avg_latency_ms']}ms)")
                status_emoji = "⚠️"
            
            if not connected:
                alerts.append("🚨 WebSocket disconnected!")
                status_emoji = "🚨"
            
            # Log summary line
            summary = (
                f"[{timestamp}] {status_emoji} "
                f"Queue: {queue_size} | "
                f"Latency: {latency:.0f}ms | "
                f"Dead: {dead_letters} | "
                f"WS: {'✓' if connected else '✗'} | "
                f"Uptime: {uptime:.0f}s | "
                f"Reconnects: {reconnects} | "
                f"Processed: {processed}"
            )
            
            log_message(summary)
            
            # Log alerts if any
            if alerts:
                for alert in alerts:
                    log_message(f"         {alert}")
                
                # Send Telegram alert for critical issues
                if dead_letters > 0 or not connected:
                    await send_telegram_alert("Critical System Alert", "\n".join(alerts))
            
            return len(alerts) == 0
            
    except httpx.ConnectError:
        log_message(f"[{timestamp}] ❌ Cannot connect to metrics endpoint. Is the system running?")
        return False
    except Exception as e:
        log_message(f"[{timestamp}] ❌ Error checking metrics: {e}")
        return False


async def send_telegram_alert(title: str, message: str):
    """Send critical alert via Telegram."""
    try:
        from app.infra.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        
        alert_text = f"<b>🚨 {title}</b>\n\n{message}\n\n<i>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        await notifier.send_message(alert_text)
        
        log_message(f"         📱 Telegram alert sent")
    except Exception as e:
        log_message(f"         ⚠️ Failed to send Telegram alert: {e}")


def log_message(message: str):
    """Log message to file and console."""
    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to file
    with open(LOG_FILE, 'a') as f:
        f.write(message + '\n')
    
    # Print to console
    print(message)


async def main():
    """Main monitoring loop."""
    print("="*70)
    print("DEPLOYMENT METRICS MONITOR")
    print("="*70)
    print(f"Monitoring: {METRICS_URL}")
    print(f"Log file: {LOG_FILE}")
    print(f"Thresholds:")
    print(f"  - Queue Size: < {THRESHOLDS['queue_size']}")
    print(f"  - Latency: < {THRESHOLDS['avg_latency_ms']}ms")
    print(f"  - Dead Letters: = {THRESHOLDS['dead_letter_count']}")
    print("="*70)
    print()
    
    # Run once
    success = await check_metrics()
    
    if success:
        print("\n✅ All metrics within thresholds")
    else:
        print("\n⚠️ Some metrics exceeded thresholds - check logs for details")
    
    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
