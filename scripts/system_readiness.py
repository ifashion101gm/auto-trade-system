#!/usr/bin/env python3
import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validation.readiness_scoring import ReadinessScorer
from app.validation.validators.strategy_validator import StrategyValidator
from app.validation.validators.risk_validator import RiskValidator
from app.validation.validators.exchange_validator import ExchangeValidator
from app.validation.validators.ai_validator import AIAgentValidator
from app.validation.validators.infra_validator import InfrastructureValidator
from app.validation.validators.monitoring_validator import MonitoringValidator
from app.validation.validators.simulation_validator import SimulationValidator
from app.validation.validators.dashboard_validator import DashboardValidator
from app.validation.validators.market_regime_validator import MarketRegimeValidator
from app.validation.validators.execution_quality_validator import ExecutionQualityValidator
from app.validation.validators.deployment_integrity_validator import DeploymentIntegrityValidator

STATUS_ICONS = {'PASS': '✅', 'FAIL': '❌', 'WARNING': '⚠️ ', 'ERROR': '🚨', 'SKIP': '➖'}


async def run_validators(mode: str = 'quick') -> 'ReadinessReport':
    print("=" * 70)
    print("PRODUCTION READINESS VALIDATION")
    print("=" * 70)
    print(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode      : {mode.upper()}")
    print("=" * 70)
    print()

    validators = [
        DeploymentIntegrityValidator(),   # Must be first — hard NO-GO on misconfig
        StrategyValidator(),
        RiskValidator(),
        ExchangeValidator(),
        ExecutionQualityValidator(),
        MarketRegimeValidator(),
        InfrastructureValidator(),
        MonitoringValidator(),
        AIAgentValidator(),
        DashboardValidator(),
        SimulationValidator(),
    ]

    if mode == 'quick':
        # Skip live simulation and market regime fetch in quick mode (<30s)
        skip = (SimulationValidator, MarketRegimeValidator)
        validators = [v for v in validators if not isinstance(v, skip)]

    results = []
    for validator in validators:
        print(f"[{validator.layer_name}]...")
        result = await validator.validate()
        results.append(result)
        icon = STATUS_ICONS.get(result.status.value, '?')
        print(f"  {icon} {result.status.value} — score {result.score:.0f}/100  "
              f"({result.checks_passed}/{result.checks_total} checks)")
        for err in result.errors:
            print(f"     ERROR: {err}")
        for w in result.warnings:
            print(f"     WARN : {w}")
        print()

    scorer = ReadinessScorer()
    report = scorer.calculate(results)

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, r in report.layer_results.items():
        icon = STATUS_ICONS.get(r.status.value, '?')
        print(f"  {icon} {name:<28} {r.status.value:<8} {r.score:.0f}/100")

    print()
    print(f"  Overall Score : {report.overall_score:.1f}/100")
    print()

    if report.is_ready():
        print("  ✅ GO — READY FOR LIMITED LIVE TRADING")
        print("     Recommended: 0.25% risk/trade, 2% daily max loss, ≤3 positions")
    else:
        print("  ❌ NO-GO — RESOLVE ISSUES BEFORE LIVE TRADING")
        for rec in report.recommendations:
            print(f"     {rec}")

    print("=" * 70)
    return report


def main():
    parser = argparse.ArgumentParser(description='Production Readiness Validation')
    parser.add_argument('--mode', choices=['quick', 'deep'], default='quick',
                        help='quick=no live sim (<30s)  deep=all layers (5-10min)')
    args = parser.parse_args()
    report = asyncio.run(run_validators(mode=args.mode))
    sys.exit(0 if report.is_ready() else 1)


if __name__ == '__main__':
    main()
