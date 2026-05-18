"""
Readiness history persistence, drift detection, and trend analysis.

Stores results in data/readiness_history.jsonl (JSON Lines — one record per line).
Kept DB-independent so it works even when the Deployment Integrity check finds
a broken DB connection.
"""
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

_HISTORY_FILE = Path(__file__).parent.parent.parent / 'data' / 'readiness_history.jsonl'
_MAX_HISTORY = 200          # Cap file at 200 records — rotate oldest
_DRIFT_LOOKBACK = 5         # Compare current run against last N runs
_DRIFT_SCORE_DROP = 10.0    # Overall score drop (points) that triggers drift alert
_DRIFT_LAYER_DROP = 20.0    # Per-layer score drop that triggers layer drift alert


@dataclass
class HistoryRecord:
    timestamp: str          # ISO-8601 UTC
    mode: str               # 'quick' | 'deep' | 'event'
    trigger: Optional[str]  # event type if event-driven, else None
    overall_score: float
    status: str             # 'READY' | 'PARTIAL' | 'NOT_READY'
    layer_scores: dict      # {layer_name: score}
    kill_triggered: bool    # True if a kill condition fired
    kill_reason: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'HistoryRecord':
        return cls(**d)


class ReadinessPersistence:
    """Save, load, and analyse readiness run history."""

    def __init__(self, history_file: Path = _HISTORY_FILE):
        self._file = history_file
        self._file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, record: HistoryRecord) -> None:
        """Append a record and enforce the file-size cap."""
        records = self._load_raw()
        records.append(record.to_dict())

        if len(records) > _MAX_HISTORY:
            records = records[-_MAX_HISTORY:]

        with self._file.open('w') as fh:
            for r in records:
                fh.write(json.dumps(r) + '\n')

    def save_from_report(
        self,
        report,           # ReadinessReport — avoid circular import
        mode: str = 'quick',
        trigger: Optional[str] = None,
    ) -> HistoryRecord:
        """Convenience: build a HistoryRecord from a ReadinessReport and save it."""
        record = HistoryRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            trigger=trigger,
            overall_score=report.overall_score,
            status=report.status,
            layer_scores={
                name: r.score for name, r in report.layer_results.items()
            },
            kill_triggered=getattr(report, 'kill_triggered', False),
            kill_reason=getattr(report, 'kill_reason', None),
        )
        self.save(record)
        return record

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load_history(self, n: int = _DRIFT_LOOKBACK) -> List[HistoryRecord]:
        """Return the last *n* records, newest-last."""
        raw = self._load_raw()
        return [HistoryRecord.from_dict(r) for r in raw[-n:]]

    def _load_raw(self) -> List[dict]:
        if not self._file.exists():
            return []
        records = []
        with self._file.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def detect_drift(self, current_score: float, current_layers: dict) -> List[str]:
        """
        Compare current run to the last _DRIFT_LOOKBACK runs.

        Returns a list of human-readable drift warnings (empty = no drift).
        """
        warnings = []
        history = self.load_history(n=_DRIFT_LOOKBACK)

        if len(history) < 2:
            return warnings  # Not enough history to detect drift

        # Overall score drift
        avg_past = sum(r.overall_score for r in history) / len(history)
        drop = avg_past - current_score
        if drop >= _DRIFT_SCORE_DROP:
            warnings.append(
                f"Overall score dropped {drop:.1f} pts "
                f"(was avg {avg_past:.1f}, now {current_score:.1f})"
            )

        # Per-layer drift — compare against each layer's average over history
        all_layer_names = set(current_layers)
        for layer in all_layer_names:
            past_scores = [
                r.layer_scores[layer]
                for r in history
                if layer in r.layer_scores
            ]
            if not past_scores:
                continue
            layer_avg = sum(past_scores) / len(past_scores)
            current_layer_score = current_layers.get(layer, 0)
            layer_drop = layer_avg - current_layer_score
            if layer_drop >= _DRIFT_LAYER_DROP:
                warnings.append(
                    f"[{layer}] score drifted down {layer_drop:.1f} pts "
                    f"(was avg {layer_avg:.1f}, now {current_layer_score:.1f})"
                )

        return warnings

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def get_score_trend(self, n: int = 10) -> dict:
        """
        Return a simple trend summary over the last *n* records.

        Keys: direction ('improving'|'degrading'|'stable'), slope, min, max, avg, count
        """
        history = self.load_history(n=n)
        if not history:
            return {'direction': 'unknown', 'slope': 0, 'count': 0}

        scores = [r.overall_score for r in history]
        count = len(scores)
        avg = sum(scores) / count

        # Linear slope via least-squares (x = index, y = score)
        if count >= 2:
            x_mean = (count - 1) / 2
            num = sum((i - x_mean) * (s - avg) for i, s in enumerate(scores))
            den = sum((i - x_mean) ** 2 for i in range(count))
            slope = num / den if den != 0 else 0.0
        else:
            slope = 0.0

        if slope > 0.5:
            direction = 'improving'
        elif slope < -0.5:
            direction = 'degrading'
        else:
            direction = 'stable'

        return {
            'direction': direction,
            'slope': round(slope, 3),
            'min': min(scores),
            'max': max(scores),
            'avg': round(avg, 1),
            'count': count,
            'last_run': history[-1].timestamp,
        }
