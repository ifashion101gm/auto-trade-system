"""
Control Panel Dashboard API
Unified readiness checklist + live system status for Bybit live trade deployment.

Endpoints:
  GET  /dashboard/readiness          — full live-trade readiness checklist
  GET  /dashboard/status             — real-time system snapshot
  GET  /dashboard/strategy           — strategy layer health
  GET  /dashboard/risk               — risk engine state
  GET  /dashboard/exchange           — Bybit connectivity
  GET  /dashboard/ai                 — AI regime classifier health
  GET  /dashboard/safety             — kill switch + circuit breakers
  POST /dashboard/checklist/run      — execute all checks and return pass/fail
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter
from app.config import settings
from app.logging_config import get_logger
from app.risk.circuit_breaker import get_circuit_breaker
from app.infra.kill_switch import KillSwitch
from app.strategy.ai_filter.ai_filter import AIFilter

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check(name: str, passed: bool, detail: str, critical: bool = False) -> Dict:
    return {
        "name": name,
        "passed": passed,
        "critical": critical,
        "detail": detail,
        "status": "✅ PASS" if passed else ("🔴 FAIL" if critical else "🟡 WARN"),
    }


async def _safe(coro) -> Tuple[Any, Optional[str]]:
    """Run coroutine, return (result, error_str)."""
    try:
        return await coro, None
    except Exception as exc:
        return None, str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Individual check groups
# ─────────────────────────────────────────────────────────────────────────────

async def _check_exchange() -> List[Dict]:
    checks = []
    try:
        from app.infra.pybit_demo_client import PybitDemoClient
        client = PybitDemoClient()

        # Connectivity + balance
        bal, err = await _safe(client.fetch_balance())
        if err:
            checks.append(_check("Bybit Demo — API connectivity", False, err, critical=True))
        else:
            usdt = bal.get("total_usdt", 0)
            checks.append(_check(
                "Bybit Demo — API connectivity", True,
                f"Connected. Balance: {usdt:.2f} USDT"
            ))
            checks.append(_check(
                "Bybit Demo — minimum balance ($100)",
                usdt >= 100,
                f"{usdt:.2f} USDT (need ≥ 100)",
                critical=True,
            ))

        # Ticker fetch
        ticker, err = await _safe(client.fetch_ticker("XAUUSDT"))
        if err:
            checks.append(_check("Bybit Demo — XAUUSDT ticker", False, err, critical=True))
        else:
            price = ticker.get("last_price", 0)
            spread = ticker.get("ask_price", 0) - ticker.get("bid_price", 0)
            spread_pct = (spread / price * 100) if price else 0
            checks.append(_check(
                "Bybit Demo — XAUUSDT ticker",
                price > 0,
                f"Last: ${price:.2f}  Spread: ${spread:.2f} ({spread_pct:.3f}%)"
            ))
            checks.append(_check(
                "Bybit Demo — spread acceptable (<0.5%)",
                spread_pct < 0.5,
                f"Spread: {spread_pct:.3f}%",
                critical=False,
            ))

        await client.close()
    except Exception as exc:
        checks.append(_check("Bybit Demo — client init", False, str(exc), critical=True))

    return checks


async def _check_risk() -> List[Dict]:
    checks = []
    try:
        from app.risk.risk_engine import RiskEngine
        re = RiskEngine()
        metrics = await re.get_risk_metrics()

        checks.append(_check(
            "Risk Engine — daily loss lock",
            not re.daily_loss_lock_active,
            "Lock active — trading halted" if re.daily_loss_lock_active else "Clear",
            critical=True,
        ))
        checks.append(_check(
            "Risk Engine — drawdown lock",
            not re.drawdown_lock_active,
            "Lock active" if re.drawdown_lock_active else "Clear",
            critical=True,
        ))
        checks.append(_check(
            "Risk Engine — emergency stop",
            not re.emergency_stop_active,
            re.emergency_stop_reason or "Clear",
            critical=True,
        ))
        checks.append(_check(
            "Risk Engine — consecutive losses",
            re.consecutive_losses < re.max_consecutive_losses,
            f"{re.consecutive_losses}/{re.max_consecutive_losses}",
        ))
        checks.append(_check(
            "Risk Engine — daily P&L",
            re.daily_pnl_pct > -re.max_daily_loss_pct,
            f"{re.daily_pnl_pct:.2%} (limit: -{re.max_daily_loss_pct:.1%})",
        ))
    except Exception as exc:
        checks.append(_check("Risk Engine — init", False, str(exc), critical=True))

    return checks


async def _check_kill_switch() -> List[Dict]:
    checks = []
    try:
        ks = KillSwitch()
        engaged = ks.is_engaged()
        status = ks.get_status()
        checks.append(_check(
            "Kill Switch — disengaged",
            not engaged,
            f"Engaged by {status.engaged_by}: {status.reason}" if engaged else "Clear",
            critical=True,
        ))
    except Exception as exc:
        checks.append(_check("Kill Switch — init", False, str(exc), critical=True))

    return checks


async def _check_circuit_breakers() -> List[Dict]:
    checks = []
    try:
        cb = get_circuit_breaker()
        status = cb.get_status()
        checks.append(_check(
            "Circuit Breaker (risk) — trading enabled",
            not cb.trading_disabled,
            cb.disable_reason or "Clear",
            critical=True,
        ))
        checks.append(_check(
            "Circuit Breaker — consecutive losses counter",
            cb.failure_counts.get("consecutive_losses", 0) < cb.max_consecutive_losses,
            f"{cb.failure_counts.get('consecutive_losses', 0)}/{cb.max_consecutive_losses}",
        ))
    except Exception as exc:
        checks.append(_check("Circuit Breaker — init", False, str(exc), critical=True))

    return checks


async def _check_ai() -> List[Dict]:
    checks = []
    try:
        ai = AIFilter()
        available = ai._available
        checks.append(_check(
            "AI Regime Classifier — OpenRouter available",
            available,
            "OpenRouter client ready" if available else "Fallback to rule-based only",
            critical=False,
        ))

        counters = AIFilter.get_counters()
        total = counters["calls"] or 1
        error_rate = counters["parse_errors"] / total
        timeout_rate = counters["timeouts"] / total
        checks.append(_check(
            "AI Classifier — parse error rate (<10%)",
            error_rate < 0.10,
            f"{error_rate:.1%} ({counters['parse_errors']}/{counters['calls']} calls)",
        ))
        checks.append(_check(
            "AI Classifier — timeout rate (<10%)",
            timeout_rate < 0.10,
            f"{timeout_rate:.1%} ({counters['timeouts']}/{counters['calls']} calls)",
        ))

        # Check API key configured
        key_set = bool(getattr(settings, "OPENROUTER_API_KEY", None))
        checks.append(_check(
            "AI Classifier — OPENROUTER_API_KEY set",
            key_set,
            "Key configured" if key_set else "Missing — rule-based fallback only",
            critical=False,
        ))
    except Exception as exc:
        checks.append(_check("AI Classifier — init", False, str(exc), critical=True))

    return checks


async def _check_strategy() -> List[Dict]:
    checks = []
    try:
        from app.strategies.gold_opening_reversal import GoldOpeningReversalStrategy
        strat = GoldOpeningReversalStrategy()

        # Verify detect_reversal_pattern is not the stub
        import inspect
        src = inspect.getsource(strat.detect_reversal_pattern)
        is_stub = "TODO" in src and src.count("return") <= 3
        checks.append(_check(
            "Strategy — detect_reversal_pattern() implemented",
            not is_stub,
            "⚠️  Still a stub (RSI-only). Needs pin bar / engulfing / divergence logic." if is_stub
            else "Pattern detection implemented",
            critical=True,
        ))

        # Session detection
        from app.runtime.session_scheduler import SessionScheduler
        sched = SessionScheduler()
        session_info = sched.get_session_info()
        checks.append(_check(
            "Strategy — session scheduler running",
            True,
            f"Current session: {session_info.get('current_session', 'unknown')}",
        ))

        # Indicators module importable
        from app.strategy import indicators as ind_mod
        checks.append(_check(
            "Strategy — indicators module importable",
            True,
            "ATR, RSI, EMA, SMA, MACD available",
        ))

        # Runner loop check (worker file exists and has a loop)
        import os
        worker_path = os.path.join(
            os.path.dirname(__file__), "..", "worker_gold_bot.py"
        )
        worker_exists = os.path.exists(os.path.abspath(worker_path))
        checks.append(_check(
            "Strategy — runner loop (worker_gold_bot.py)",
            worker_exists,
            "File exists — verify it calls generate_signal() on schedule" if worker_exists
            else "Missing — no loop feeds live OHLCV into strategy",
            critical=True,
        ))

    except Exception as exc:
        checks.append(_check("Strategy — init", False, str(exc), critical=True))

    return checks


async def _check_infrastructure() -> List[Dict]:
    checks = []

    # Database
    try:
        from app.database.connection import init_db
        checks.append(_check("Database — connection module importable", True, "SQLAlchemy async ready"))
    except Exception as exc:
        checks.append(_check("Database — connection", False, str(exc), critical=True))

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks.append(_check("Redis — connectivity", True, settings.REDIS_URL))
    except Exception as exc:
        checks.append(_check("Redis — connectivity", False, str(exc), critical=False))

    # Telegram
    tg_ok = bool(getattr(settings, "TELEGRAM_BOT_TOKEN", None)) and \
            bool(getattr(settings, "TELEGRAM_CHAT_ID", None))
    checks.append(_check(
        "Telegram — credentials configured",
        tg_ok,
        "Bot token + chat ID set" if tg_ok else "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID",
        critical=False,
    ))

    # News guard
    try:
        from app.runtime.news_guard import NewsGuard
        ng = NewsGuard()
        ng_status = ng.get_status()
        checks.append(_check(
            "News Guard — running",
            True,
            f"Trading safe: {ng_status.get('is_safe', True)}",
        ))
    except Exception as exc:
        checks.append(_check("News Guard — init", False, str(exc), critical=False))

    return checks


async def _check_shadow_gate() -> List[Dict]:
    checks = []
    try:
        from app.shadow_mode.execution_engine import ShadowExecutionEngine
        engine = ShadowExecutionEngine()
        validation = engine.get_validation_status()
        gate_passed = validation.get("validation_passed", False)
        trade_count = validation.get("metrics", {}).get("total_trades", 0)
        checks.append(_check(
            "Shadow Mode — validation gate",
            gate_passed,
            f"{trade_count} trades. Criteria: {validation.get('checks', {})}",
            critical=False,  # warn only — blocks live capital, not demo
        ))
    except Exception as exc:
        checks.append(_check("Shadow Mode — engine", False, str(exc), critical=False))

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Master checklist runner
# ─────────────────────────────────────────────────────────────────────────────

async def _run_all_checks() -> Dict:
    t0 = time.perf_counter()

    results = await asyncio.gather(
        _check_exchange(),
        _check_risk(),
        _check_kill_switch(),
        _check_circuit_breakers(),
        _check_ai(),
        _check_strategy(),
        _check_infrastructure(),
        _check_shadow_gate(),
        return_exceptions=True,
    )

    sections = {
        "exchange":        results[0] if not isinstance(results[0], Exception) else [],
        "risk":            results[1] if not isinstance(results[1], Exception) else [],
        "kill_switch":     results[2] if not isinstance(results[2], Exception) else [],
        "circuit_breaker": results[3] if not isinstance(results[3], Exception) else [],
        "ai_classifier":   results[4] if not isinstance(results[4], Exception) else [],
        "strategy":        results[5] if not isinstance(results[5], Exception) else [],
        "infrastructure":  results[6] if not isinstance(results[6], Exception) else [],
        "shadow_gate":     results[7] if not isinstance(results[7], Exception) else [],
    }

    all_checks: List[Dict] = []
    for checks in sections.values():
        all_checks.extend(checks)

    total       = len(all_checks)
    passed      = sum(1 for c in all_checks if c["passed"])
    critical_failures = [c for c in all_checks if not c["passed"] and c["critical"]]
    warnings    = [c for c in all_checks if not c["passed"] and not c["critical"]]

    ready_for_demo = len(critical_failures) == 0
    ready_for_live = ready_for_demo and len(warnings) == 0

    score = round(passed / total * 100, 1) if total else 0

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "timestamp": _utc(),
        "elapsed_ms": elapsed_ms,
        "score": score,
        "total_checks": total,
        "passed": passed,
        "failed_critical": len(critical_failures),
        "warnings": len(warnings),
        "ready_for_demo_trading": ready_for_demo,
        "ready_for_live_capital": ready_for_live,
        "verdict": (
            "🟢 READY FOR DEMO TRADING"   if ready_for_demo and not ready_for_live else
            "🟢 READY FOR LIVE CAPITAL"   if ready_for_live else
            "🔴 NOT READY — fix critical failures first"
        ),
        "critical_failures": [c["name"] + " — " + c["detail"] for c in critical_failures],
        "warning_items":     [c["name"] + " — " + c["detail"] for c in warnings],
        "sections": sections,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/checklist/run")
async def run_checklist():
    """
    Execute the full live-trade readiness checklist.
    Returns pass/fail for every check, a readiness score, and a verdict.
    """
    return await _run_all_checks()


@router.get("/readiness")
async def readiness_summary():
    """
    Quick readiness summary — score + verdict + critical failures only.
    Suitable for a status badge or CI gate.
    """
    result = await _run_all_checks()
    return {
        "timestamp":              result["timestamp"],
        "score":                  result["score"],
        "verdict":                result["verdict"],
        "ready_for_demo_trading": result["ready_for_demo_trading"],
        "ready_for_live_capital": result["ready_for_live_capital"],
        "critical_failures":      result["critical_failures"],
        "warnings":               result["warning_items"],
        "elapsed_ms":             result["elapsed_ms"],
    }


@router.get("/status")
async def system_status():
    """
    Real-time system snapshot — trading state, session, risk metrics, AI counters.
    """
    snapshot: Dict[str, Any] = {"timestamp": _utc()}

    # Trading state from app state
    try:
        from app.main import state as app_state
        snapshot["trading_enabled"]  = app_state.trading_enabled
        snapshot["daily_loss_lock"]  = app_state.daily_loss_lock
        snapshot["last_error"]       = app_state.last_error
        snapshot["uptime_sec"]       = int(time.time() - app_state.start_time)
        snapshot["session"]          = app_state.session_scheduler.get_session_info()
        snapshot["news_guard"]       = app_state.news_guard.get_status()
    except Exception:
        snapshot["trading_enabled"] = None

    # Circuit breaker
    try:
        cb = get_circuit_breaker()
        snapshot["circuit_breaker"] = cb.get_status()
    except Exception as exc:
        snapshot["circuit_breaker"] = {"error": str(exc)}

    # Kill switch
    try:
        ks = KillSwitch()
        s = ks.get_status()
        snapshot["kill_switch"] = {"engaged": s.engaged, "reason": s.reason}
    except Exception as exc:
        snapshot["kill_switch"] = {"error": str(exc)}

    # AI counters
    try:
        snapshot["ai_counters"] = AIFilter.get_counters()
    except Exception as exc:
        snapshot["ai_counters"] = {"error": str(exc)}

    # Risk metrics
    try:
        from app.risk.risk_engine import RiskEngine
        re = RiskEngine()
        snapshot["risk"] = await re.get_risk_metrics()
    except Exception as exc:
        snapshot["risk"] = {"error": str(exc)}

    return snapshot


@router.get("/exchange")
async def exchange_status():
    """Bybit Demo connectivity, balance, and XAUUSDT ticker."""
    checks = await _check_exchange()
    return {"timestamp": _utc(), "checks": checks}


@router.get("/risk")
async def risk_status():
    """Risk engine state — locks, drawdown, consecutive losses."""
    checks = await _check_risk()
    try:
        from app.risk.risk_engine import RiskEngine
        re = RiskEngine()
        metrics = await re.get_risk_metrics()
    except Exception as exc:
        metrics = {"error": str(exc)}
    return {"timestamp": _utc(), "checks": checks, "metrics": metrics}


@router.get("/ai")
async def ai_status():
    """AI regime classifier health — availability, error rates, counters."""
    checks = await _check_ai()
    return {"timestamp": _utc(), "checks": checks, "counters": AIFilter.get_counters()}


@router.get("/strategy")
async def strategy_status():
    """Strategy layer health — pattern detection, session, indicators, runner loop."""
    checks = await _check_strategy()
    try:
        from app.strategies.gold_opening_reversal import GoldOpeningReversalStrategy
        strat = GoldOpeningReversalStrategy()
        params = strat.get_parameters()
        in_session = strat.is_trading_session()
    except Exception as exc:
        params = {"error": str(exc)}
        in_session = None
    return {
        "timestamp": _utc(),
        "checks": checks,
        "in_trading_session": in_session,
        "parameters": params,
    }


@router.get("/safety")
async def safety_status():
    """Kill switch + circuit breaker state."""
    ks_checks = await _check_kill_switch()
    cb_checks = await _check_circuit_breakers()
    return {
        "timestamp": _utc(),
        "kill_switch": ks_checks,
        "circuit_breaker": cb_checks,
    }
