"""
Global Kill Switch

Provides a safe, auditable global kill switch that can pause trading activities.
State is optionally persisted to disk (JSON) to survive restarts.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from typing import Optional

from app.logging_config import get_logger
from app.notifications.notifier import TelegramNotifier
from app.config import settings

logger = get_logger(__name__)


@dataclass
class KillSwitchStatus:
    engaged: bool = False
    engaged_by: Optional[str] = None
    reason: Optional[str] = None
    timestamp: Optional[str] = None


class KillSwitch:
    def __init__(self, notifier: Optional[TelegramNotifier] = None, persist_path: Optional[str] = None):
        self.notifier = notifier
        self.persist_path = persist_path or getattr(settings, 'KILL_SWITCH_STATE_FILE', '.kill_switch_state.json')
        self.status = KillSwitchStatus()

        # Load persisted state if present
        try:
            if os.path.exists(self.persist_path):
                with open(self.persist_path, 'r') as f:
                    data = json.load(f)
                    self.status = KillSwitchStatus(**data)
                    logger.info(f"Loaded kill switch state from {self.persist_path}")
        except Exception as e:
            logger.warning(f"Failed to load kill switch state: {e}")

    def is_engaged(self) -> bool:
        return bool(self.status.engaged)

    def engage(self, actor: str = 'system', reason: str = 'manual') -> KillSwitchStatus:
        self.status.engaged = True
        self.status.engaged_by = actor
        self.status.reason = reason
        self.status.timestamp = datetime.now(timezone.utc).isoformat()
        self._persist()

        logger.critical(f"KILL SWITCH ENGAGED by {actor}: {reason}")
        try:
            if self.notifier:
                self.notifier.send_kill_switch_alert(actor=actor, reason=reason)
        except Exception as e:
            logger.error(f"Failed to send kill switch alert: {e}")

        return self.status

    def disengage(self, actor: str = 'system', reason: str = 'manual_clear') -> KillSwitchStatus:
        self.status.engaged = False
        self.status.engaged_by = actor
        self.status.reason = reason
        self.status.timestamp = datetime.now(timezone.utc).isoformat()
        self._persist()

        logger.info(f"Kill switch disengaged by {actor}: {reason}")
        try:
            if self.notifier:
                self.notifier.send_kill_switch_cleared(actor=actor, reason=reason)
        except Exception as e:
            logger.error(f"Failed to send kill switch cleared alert: {e}")

        return self.status

    def get_status(self) -> KillSwitchStatus:
        return self.status

    def _persist(self):
        try:
            with open(self.persist_path, 'w') as f:
                json.dump(asdict(self.status), f)
        except Exception as e:
            logger.warning(f"Failed to persist kill switch state: {e}")
