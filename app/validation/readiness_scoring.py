"""
Readiness scoring engine with 4-layer enterprise architecture,
kill conditions, and drift-aware reporting.

Architecture layers:
  Operational        — Infra, Exchange, Risk, Monitoring, Dashboard
  Trading Intel      — Strategy, Market Regime, Execution Quality, Liquidity, AI Agents
  Governance         — Deployment Integrity  (kill conditions live here)
  Persistence        — handled by ReadinessPersistence, not scored
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .validators.base_validator import ValidationResult, ValidationStatus

# ---------------------------------------------------------------------------
# Layer grouping — maps layer_name → architecture bucket
# ---------------------------------------------------------------------------
LAYER_ARCHITECTURE = {
    # Operational
    'Infrastructure':        'Operational',
    'Exchange Connectivity': 'Operational',
    'Risk Engine':           'Operational',
    'Monitoring Systems':    'Operational',
    'Dashboard API':         'Operational',
    # Trading Intelligence
    'Strategy':              'Trading Intelligence',
    'Market Regime':         'Trading Intelligence',
    'Execution Quality':     'Trading Intelligence',
    'Liquidity':             'Trading Intelligence',
    'AI Agents':             'Trading Intelligence',
    # Governance
    'Deployment Integrity':  'Governance',
    # Deep-mode only
    'Live Simulation':       'Operational',
}

# Weights — must sum to 100 across all active validators
LAYER_WEIGHTS = {
    'Strategy':              18,
    'Risk Engine':           13,
    'Deployment Integrity':  13,
    'Exchange Connectivity': 10,
    'Execution Quality':      8,
    'Infrastructure':         8,
    'Liquidity':              8,
    'Market Regime':          7,
    'Live Simulation':        5,
    'Monitoring Systems':     5,
    'AI Agents':              3,
    'Dashboard API':          2,
}

READY_THRESHOLD   = 85.0
PARTIAL_THRESHOLD = 70.0

# ---------------------------------------------------------------------------
# Kill conditions — any match → hard NO-GO regardless of overall score
# ---------------------------------------------------------------------------
# Each entry: (layer_name, predicate, reason_template)
KILL_CONDITIONS = [
    (
        'Deployment Integrity',
        lambda r: r.status == ValidationStatus.FAIL,
        'Deployment misconfigured — fix env/secrets/DB migration before going live',
    ),
    (
        'Risk Engine',
        lambda r: r.score < 60,
        'Risk engine health critically low ({score:.0f}/100) — limits may be unset',
    ),
    (
        'Exchange Connectivity',
        lambda r: r.status == ValidationStatus.FAIL,
        'Cannot reach exchange — trading would fail immediately',
    ),
    (
        'Liquidity',
        lambda r: r.status == ValidationStatus.FAIL,
        'Market liquidity insufficient — execution cost unacceptable',
    ),
]


@dataclass
class ReadinessReport:
    overall_score: float
    status: str                          # 'READY' | 'PARTIAL' | 'NOT_READY'
    layer_results: Dict[str, ValidationResult]
    recommendations: List[str]
    kill_triggered: bool = False
    kill_reason: Optional[str] = None
    drift_warnings: List[str] = field(default_factory=list)
    layer_groups: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def is_ready(self) -> bool:
        return not self.kill_triggered and self.overall_score >= READY_THRESHOLD


class ReadinessScorer:

    def calculate(
        self,
        results: List[ValidationResult],
        drift_warnings: Optional[List[str]] = None,
    ) -> ReadinessReport:

        # Weighted score
        total_score = 0.0
        for result in results:
            weight = LAYER_WEIGHTS.get(result.layer_name, 0)
            total_score += (result.score / 100.0) * weight

        # Status label
        if total_score >= READY_THRESHOLD:
            status = 'READY'
        elif total_score >= PARTIAL_THRESHOLD:
            status = 'PARTIAL'
        else:
            status = 'NOT_READY'

        layer_results = {r.layer_name: r for r in results}

        # Kill condition evaluation
        kill_triggered = False
        kill_reason: Optional[str] = None
        for layer_name, predicate, reason_template in KILL_CONDITIONS:
            result = layer_results.get(layer_name)
            if result and predicate(result):
                kill_triggered = True
                kill_reason = reason_template.format(score=result.score)
                status = 'NOT_READY'
                break

        # Layer group scores (avg score per architecture bucket)
        layer_groups: Dict[str, Dict[str, float]] = {}
        for result in results:
            bucket = LAYER_ARCHITECTURE.get(result.layer_name, 'Other')
            if bucket not in layer_groups:
                layer_groups[bucket] = {}
            layer_groups[bucket][result.layer_name] = result.score

        return ReadinessReport(
            overall_score=total_score,
            status=status,
            layer_results=layer_results,
            recommendations=self._generate_recommendations(results, kill_triggered, kill_reason),
            kill_triggered=kill_triggered,
            kill_reason=kill_reason,
            drift_warnings=drift_warnings or [],
            layer_groups=layer_groups,
        )

    def _generate_recommendations(
        self,
        results: List[ValidationResult],
        kill_triggered: bool,
        kill_reason: Optional[str],
    ) -> List[str]:
        recs = []

        if kill_triggered and kill_reason:
            recs.append(f'🔴 KILL CONDITION: {kill_reason}')

        for r in results:
            if r.status == ValidationStatus.FAIL:
                recs.append(f'[FAIL] {r.layer_name}: {r.checks_passed}/{r.checks_total} checks passed')
                for err in r.errors:
                    recs.append(f'  • {err}')
                for d in r.details:
                    if d.get('status') == 'FAIL':
                        note = d.get('note') or d.get('value') or ''
                        recs.append(f'  ✗ {d["check"]}: {note}')
            elif r.status == ValidationStatus.WARNING:
                for w in r.warnings:
                    recs.append(f'[WARN] {r.layer_name}: {w}')
                for d in r.details:
                    if d.get('status') == 'WARNING':
                        note = d.get('note') or d.get('value') or ''
                        recs.append(f'  ⚠ {d["check"]}: {note}')

        return recs
