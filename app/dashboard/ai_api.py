"""
AI orchestration API endpoints for monitoring and control.
"""
from fastapi import APIRouter, HTTPException, Depends
from app.ai_agents.orchestrator import AIAgentOrchestrator

router = APIRouter()

def get_orchestrator() -> AIAgentOrchestrator:
    """Dependency for getting the AI orchestrator instance."""
    return AIAgentOrchestrator()


@router.post("/ai/run-cycle")
async def run_ai_cycle(orchestrator: AIAgentOrchestrator = Depends(get_orchestrator), market_data: dict = None):
    """
    Run AI analysis cycle with parallel agent execution.
    
    Demonstrates Zone C optimization: parallel stages reduce latency.
    """
    if market_data is None:
        market_data = {"volatility": 0.5}
    
    result = await orchestrator.run_cycle_parallel(market_data)
    return result


@router.get("/ai/status")
async def get_orchestrator_status(orchestrator: AIAgentOrchestrator = Depends(get_orchestrator)):
    """Get current orchestrator status including circuit breaker state."""
    return orchestrator.status


@router.post("/ai/pause")
async def pause_orchestrator(reason: str = "Manual pause", orchestrator: AIAgentOrchestrator = Depends(get_orchestrator)):
    """Pause the orchestrator (circuit breaker)."""
    orchestrator.pause(reason)
    return {"status": "paused", "reason": reason}


@router.post("/ai/resume")
async def resume_orchestrator(orchestrator: AIAgentOrchestrator = Depends(get_orchestrator)):
    """Resume the orchestrator."""
    orchestrator.resume()
    return {"status": "resumed"}


@router.get("/ai/benchmark")
async def benchmark_performance(orchestrator: AIAgentOrchestrator = Depends(get_orchestrator)):
    """
    Benchmark sequential vs parallel execution.
    
    Shows the performance improvement from Zone C optimization.
    """
    test_data = {"volatility": 0.5}
    
    # Run sequential (baseline)
    seq_result = await orchestrator.run_cycle_sequential(test_data)
    
    # Run parallel (optimized)
    par_result = await orchestrator.run_cycle_parallel(test_data)
    
    improvement = ((seq_result["cycle_time_ms"] - par_result["cycle_time_ms"]) / 
                   seq_result["cycle_time_ms"] * 100)
    
    return {
        "sequential_ms": seq_result["cycle_time_ms"],
        "parallel_ms": par_result["cycle_time_ms"],
        "improvement_pct": round(improvement, 2),
        "speedup_factor": round(seq_result["cycle_time_ms"] / par_result["cycle_time_ms"], 2)
    }
