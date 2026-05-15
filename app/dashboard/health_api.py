"""
Health Check & Reconciliation Dashboard API.

Provides endpoints for:
- Public health checks (/health)
- Detailed system status (/health/detailed)
- Reconciliation status and metrics (/reconciliation/status)
- Real-time watchdog monitoring (/watchdogs/status)

These endpoints support observability and operational monitoring.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health", "monitoring"])


# ============================================================================
# Response Models
# ============================================================================

class HealthStatusResponse(BaseModel):
    """Public health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str = "2.0.0"


class ComponentHealth(BaseModel):
    """Individual component health status."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    last_check: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with all components."""
    status: str
    timestamp: str
    components: Dict[str, ComponentHealth]
    uptime_seconds: Optional[float] = None
    active_trading_session: bool = False


class ReconciliationStatusResponse(BaseModel):
    """Reconciliation engine status."""
    is_running: bool
    last_run: Optional[str] = None
    total_runs: int
    total_mismatches_detected: int
    reconciliation_interval_seconds: int
    auto_repair_enabled: bool
    exchange: str
    testnet: bool
    next_run_in_seconds: Optional[float] = None


class WatchdogStatusResponse(BaseModel):
    """Watchdog orchestrator status."""
    is_running: bool
    watchdogs: Dict[str, Dict[str, Any]]
    aggregated_status: str
    last_health_check: Optional[str] = None


# ============================================================================
# Public Health Endpoint
# ============================================================================

@router.get("/health", response_model=HealthStatusResponse)
async def health_check():
    """
    Public health check endpoint.
    
    Returns basic system status without authentication.
    Suitable for load balancer health checks and uptime monitoring.
    
    Returns:
        HealthStatusResponse with overall system status
    """
    try:
        # Quick checks to determine overall health
        status = "healthy"
        
        # In production, you might check:
        # - Database connectivity (quick ping)
        # - Exchange API availability (cached status)
        # - Memory usage (< critical threshold)
        
        return HealthStatusResponse(
            status=status,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthStatusResponse(
            status="unhealthy",
            timestamp=datetime.utcnow().isoformat()
        )


# ============================================================================
# Detailed Health Endpoint (Authenticated)
# ============================================================================

@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check endpoint with full component status.
    
    Requires authentication in production (add Depends(get_current_user)).
    Returns comprehensive system health including watchdogs, database,
    exchange connectivity, and circuit breaker state.
    
    Returns:
        DetailedHealthResponse with all component statuses
    """
    try:
        # Lazy import to avoid circular dependency
        from app.main import state
        components = {}
        overall_status = "healthy"
        
        # Check watchdog orchestrator
        if state.watchdog_orchestrator:
            watchdog_health = await state.watchdog_orchestrator.get_aggregated_health_report()
            
            components['watchdogs'] = ComponentHealth(
                name="Self-Healing Watchdogs",
                status=watchdog_health.get('overall_status', 'unknown'),
                last_check=watchdog_health.get('timestamp'),
                details={
                    'api': watchdog_health.get('watchdogs', {}).get('api', {}),
                    'database': watchdog_health.get('watchdogs', {}).get('database', {}),
                    'memory': watchdog_health.get('watchdogs', {}).get('memory', {}),
                    'queue': watchdog_health.get('watchdogs', {}).get('queue', {})
                }
            )
            
            # Update overall status if any watchdog is unhealthy
            if watchdog_health.get('overall_status') == 'unhealthy':
                overall_status = "unhealthy"
            elif watchdog_health.get('overall_status') == 'degraded' and overall_status == "healthy":
                overall_status = "degraded"
        
        # Check trading service
        if hasattr(state, 'trading_service') and state.trading_service:
            ts_health = state.trading_service.get_state_metrics()
            components['trading_service'] = ComponentHealth(
                name="Trading Service",
                status="healthy",
                details={
                    'current_state': ts_health.get('current_state'),
                    'total_transitions': ts_health.get('total_transitions')
                }
            )
        
        # Check reconciliation engine
        if hasattr(state, 'trading_service') and state.trading_service:
            recon_engine = state.trading_service.reconciliation_engine
            recon_stats = recon_engine.get_detailed_status()
            components['reconciliation'] = ComponentHealth(
                name="Reconciliation Engine",
                status="healthy" if recon_stats['is_running'] else "stopped",
                last_check=recon_stats.get('last_run'),
                details=recon_stats
            )
        
        # Check circuit breaker
        if hasattr(state, 'trading_service') and state.trading_service:
            cb = state.trading_service.circuit_breaker
            components['circuit_breaker'] = ComponentHealth(
                name="Circuit Breaker",
                status="open" if cb.trading_disabled else "closed",
                details={
                    'trading_disabled': cb.trading_disabled,
                    'disable_reason': cb.disable_reason,
                    'failure_counts': dict(cb.failure_counts)
                }
            )
            
            if cb.trading_disabled:
                overall_status = "degraded"
        
        # Calculate uptime (if available)
        uptime_seconds = None
        if hasattr(state, 'startup_time'):
            uptime_seconds = (datetime.utcnow() - state.startup_time).total_seconds()
        
        # Check active trading session
        active_session = False
        if hasattr(state, 'trading_session_scheduler'):
            active_session = state.trading_session_scheduler.is_active_session()
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            components=components,
            uptime_seconds=uptime_seconds,
            active_trading_session=active_session
        )
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# ============================================================================
# Reconciliation Status Endpoint
# ============================================================================

@router.get("/reconciliation/status", response_model=ReconciliationStatusResponse)
async def reconciliation_status():
    """
    Get reconciliation engine status and statistics.
    
    Returns current reconciliation configuration, run history,
    mismatch detection stats, and next scheduled run time.
    
    Returns:
        ReconciliationStatusResponse with engine status
    """
    try:
        from app.main import state
        
        if not hasattr(state, 'trading_service') or not state.trading_service:
            raise HTTPException(status_code=503, detail="Trading service not initialized")
        
        recon_engine = state.trading_service.reconciliation_engine
        stats = recon_engine.get_detailed_status()
        
        return ReconciliationStatusResponse(
            is_running=stats['is_running'],
            last_run=stats['last_run'],
            total_runs=stats['total_runs'],
            total_mismatches_detected=stats['total_mismatches_detected'],
            reconciliation_interval_seconds=stats['reconciliation_interval_seconds'],
            auto_repair_enabled=stats['auto_repair_enabled'],
            exchange=stats['exchange'],
            testnet=stats['testnet'],
            next_run_in_seconds=stats['next_run_in_seconds']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reconciliation status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get reconciliation status: {str(e)}")


# ============================================================================
# Watchdog Status Endpoint
# ============================================================================

@router.get("/watchdogs/status", response_model=WatchdogStatusResponse)
async def watchdog_status():
    """
    Get real-time watchdog orchestrator status.
    
    Returns health status of all 4 watchdogs (API, Database, Memory, Queue)
    with detailed metrics and last check timestamps.
    
    Returns:
        WatchdogStatusResponse with watchdog health data
    """
    try:
        from app.main import state
        
        if not state.watchdog_orchestrator:
            raise HTTPException(status_code=503, detail="Watchdog orchestrator not initialized")
        
        # Get aggregated health report
        health_report = await state.watchdog_orchestrator.get_aggregated_health_report()
        
        return WatchdogStatusResponse(
            is_running=state.watchdog_orchestrator.is_running,
            watchdogs=health_report.get('watchdogs', {}),
            aggregated_status=health_report.get('overall_status', 'unknown'),
            last_health_check=health_report.get('timestamp')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Watchdog status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get watchdog status: {str(e)}")


# ============================================================================
# Metrics Summary Endpoint (for Grafana/Prometheus scraping)
# ============================================================================

@router.get("/metrics/summary")
async def metrics_summary():
    """
    Get summary metrics for external monitoring systems.
    
    Returns key performance indicators in a format suitable for
    Prometheus scraping or Grafana dashboard visualization.
    
    Returns:
        Dictionary with system metrics
    """
    try:
        from app.main import state
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': {
                'status': 'running',
                'uptime_seconds': None
            },
            'trading': {
                'active_session': False,
                'current_state': 'idle'
            },
            'reconciliation': {
                'enabled': False,
                'last_run': None,
                'mismatches_total': 0
            },
            'watchdogs': {
                'enabled': False,
                'overall_status': 'unknown'
            }
        }
        
        # Add uptime if available
        if hasattr(state, 'startup_time'):
            metrics['system']['uptime_seconds'] = (
                datetime.utcnow() - state.startup_time
            ).total_seconds()
        
        # Add trading service metrics
        if hasattr(state, 'trading_service') and state.trading_service:
            ts = state.trading_service
            metrics['trading']['current_state'] = ts.current_state.value
            
            # Check active session
            if hasattr(state, 'trading_session_scheduler'):
                metrics['trading']['active_session'] = (
                    state.trading_session_scheduler.is_active_session()
                )
            
            # Add reconciliation metrics
            recon = ts.reconciliation_engine
            recon_stats = recon.get_detailed_status()
            metrics['reconciliation'].update({
                'enabled': recon_stats['is_running'],
                'last_run': recon_stats['last_run'],
                'mismatches_total': recon_stats['total_mismatches_detected'],
                'interval_seconds': recon_stats['reconciliation_interval_seconds']
            })
        
        # Add watchdog metrics
        if state.watchdog_orchestrator:
            health = await state.watchdog_orchestrator.get_aggregated_health_report()
            metrics['watchdogs'].update({
                'enabled': state.watchdog_orchestrator.is_running,
                'overall_status': health.get('overall_status', 'unknown')
            })
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics summary failed: {e}")
        return {'error': str(e), 'timestamp': datetime.utcnow().isoformat()}


def register_health_routes(app):
    """
    Register health check routes with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    app.include_router(router)
    logger.info("✅ Health check and monitoring routes registered")
