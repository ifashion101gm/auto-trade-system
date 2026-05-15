"""
Replay Engine

Minimal event replay engine that reads timestamped JSONL events and invokes
registered handlers in timestamp order. Supports time-scaling to speed up or
slow down replay for debugging and deterministic recovery testing.
"""
import json
import time
from typing import Callable, Dict, Any
from datetime import datetime

from app.logging_config import get_logger

logger = get_logger(__name__)


class ReplayEngine:
    def __init__(self):
        self.handlers = {}

    def register_handler(self, event_type: str, fn: Callable[[Dict[str, Any]], None]):
        self.handlers[event_type] = fn

    def _parse_event(self, line: str) -> Dict[str, Any]:
        data = json.loads(line)
        # Expect `timestamp` field as ISO8601
        if 'timestamp' in data:
            try:
                data['_ts'] = datetime.fromisoformat(data['timestamp']).timestamp()
            except Exception:
                data['_ts'] = time.time()
        else:
            data['_ts'] = time.time()

        return data

    def replay(self, logfile_path: str, speed: float = 1.0):
        """Replay events from `logfile_path`.

        Args:
            logfile_path: Path to JSONL event log (each line is a JSON event)
            speed: 1.0 = real-time, 2.0 = twice as fast, 0 = no-wait (instant)
        """
        events = []

        with open(logfile_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = self._parse_event(line)
                    events.append(ev)
                except Exception as e:
                    logger.warning(f"Skipping invalid log line: {e}")

        # Sort by parsed timestamp
        events.sort(key=lambda e: e.get('_ts', 0))

        if not events:
            logger.info("No events to replay")
            return

        start_ts = events[0]['_ts']
        replay_start = time.time()

        for ev in events:
            target_offset = (ev['_ts'] - start_ts)
            if speed > 0:
                target_wall = replay_start + target_offset / speed
                now = time.time()
                sleep_for = target_wall - now
                if sleep_for > 0:
                    time.sleep(sleep_for)

            etype = ev.get('type') or ev.get('event') or 'unknown'
            handler = self.handlers.get(etype)
            logger.debug(f"Replaying event {etype} at {ev.get('timestamp')}")
            if handler:
                try:
                    handler(ev)
                except Exception as e:
                    logger.exception(f"Handler for {etype} raised: {e}")
            else:
                logger.info(f"No handler for event type: {etype}")
