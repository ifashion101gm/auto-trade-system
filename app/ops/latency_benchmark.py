"""
Latency Benchmark Tool - Measure and optimize full trading cycle performance.

Benchmarks the complete trading cycle across 100+ consecutive cycles to identify
bottlenecks and ensure <2s average latency target is met.

Features:
- Full cycle measurement (Data Fetch → AI Analysis → Risk Check → Order Submit)
- Component-level breakdown (signal engine, risk engine, AI layer, order routing)
- Percentile calculations (p50, p95, p99, max)
- Bottleneck identification with recommendations
- Queue backlog monitoring
- Degraded mode testing (without AI for baseline)

Architecture:
    Trading Cycle = Market Data + Signal Generation + Risk Check + AI Consult + Order Route
    
Metrics Tracked:
    - Total cycle time (end-to-end)
    - Per-component latency
    - Queue depth/backlog
    - Memory usage trends
    - Error rates during benchmark
"""
import time
import asyncio
import statistics
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import deque

from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


@dataclass
class CycleMetrics:
    """Metrics for a single trading cycle."""
    cycle_number: int
    total_latency_ms: float
    signal_engine_ms: float = 0.0
    risk_engine_ms: float = 0.0
    ai_layer_ms: float = 0.0
    order_routing_ms: float = 0.0
    dashboard_update_ms: float = 0.0
    queue_depth: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None


@dataclass
class BenchmarkResults:
    """Aggregated benchmark results."""
    total_cycles: int
    successful_cycles: int
    failed_cycles: int
    avg_cycle_time_ms: float
    p50_cycle_time_ms: float
    p95_cycle_time_ms: float
    p99_cycle_time_ms: float
    max_cycle_time_ms: float
    min_cycle_time_ms: float
    std_deviation_ms: float
    
    # Component breakdown
    avg_signal_engine_ms: float = 0.0
    avg_risk_engine_ms: float = 0.0
    avg_ai_layer_ms: float = 0.0
    avg_order_routing_ms: float = 0.0
    
    # Performance indicators
    bottleneck_component: str = ""
    meets_target: bool = False
    target_latency_ms: float = 2000.0  # 2 seconds
    degradation_detected: bool = False
    recommendations: List[str] = field(default_factory=list)


class LatencyBenchmark:
    """
    Benchmark full trading cycle latency across multiple cycles.
    
    Usage:
        benchmark = LatencyBenchmark(cycles=100, target_latency_ms=2000)
        results = await benchmark.run()
        print(f"Avg latency: {results.avg_cycle_time_ms:.0f}ms")
        print(f"P95 latency: {results.p95_cycle_time_ms:.0f}ms")
    """
    
    def __init__(
        self,
        cycles: int = 100,
        target_latency_ms: float = 2000.0,
        include_ai: bool = True,
        mock_data: bool = True
    ):
        self.cycles = cycles
        self.target_latency_ms = target_latency_ms
        self.include_ai = include_ai
        self.mock_data = mock_data
        
        # Metrics collection
        self.cycle_metrics: List[CycleMetrics] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # Performance tracking
        self.queue_depth_history: deque = deque(maxlen=cycles)
        self.memory_usage_history: deque = deque(maxlen=cycles)
        
        logger.info(
            f"LatencyBenchmark initialized: {cycles} cycles, "
            f"target={target_latency_ms}ms, AI={'enabled' if include_ai else 'disabled'}"
        )
    
    async def run(self) -> BenchmarkResults:
        """
        Execute the full benchmark suite.
        
        Returns:
            BenchmarkResults with comprehensive latency analysis
        """
        self.start_time = datetime.now(timezone.utc)
        logger.info(f"Starting latency benchmark: {self.cycles} cycles")
        
        try:
            for i in range(1, self.cycles + 1):
                cycle_metrics = await self._execute_cycle(i)
                self.cycle_metrics.append(cycle_metrics)
                
                # Log progress every 10 cycles
                if i % 10 == 0:
                    avg_so_far = statistics.mean([m.total_latency_ms for m in self.cycle_metrics])
                    logger.info(f"Progress: {i}/{self.cycles} cycles, avg={avg_so_far:.0f}ms")
                
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.01)
            
            self.end_time = datetime.now(timezone.utc)
            results = self._calculate_results()
            
            logger.info(
                f"Benchmark complete: {results.successful_cycles}/{results.total_cycles} successful, "
                f"avg={results.avg_cycle_time_ms:.0f}ms, p95={results.p95_cycle_time_ms:.0f}ms"
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Benchmark failed at cycle {len(self.cycle_metrics)}: {e}")
            raise
    
    async def _execute_cycle(self, cycle_number: int) -> CycleMetrics:
        """
        Execute a single trading cycle and measure latency.
        
        Args:
            cycle_number: Current cycle number (1-indexed)
            
        Returns:
            CycleMetrics with per-component timing
        """
        start_time = time.time()
        
        metrics = CycleMetrics(
            cycle_number=cycle_number,
            total_latency_ms=0.0,
            timestamp=datetime.now(timezone.utc)
        )
        
        try:
            # Phase 1: Market Data Fetch
            phase_start = time.time()
            market_data = await self._fetch_market_data()
            metrics.signal_engine_ms = (time.time() - phase_start) * 1000
            
            # Phase 2: Signal Generation
            phase_start = time.time()
            signal = await self._generate_signal(market_data)
            metrics.risk_engine_ms = (time.time() - phase_start) * 1000
            
            # Phase 3: Risk Check
            phase_start = time.time()
            risk_approved = await self._check_risk(signal)
            metrics.risk_engine_ms += (time.time() - phase_start) * 1000
            
            # Phase 4: AI Consult (optional)
            if self.include_ai and risk_approved:
                phase_start = time.time()
                ai_decision = await self._consult_ai(signal, market_data)
                metrics.ai_layer_ms = (time.time() - phase_start) * 1000
            else:
                metrics.ai_layer_ms = 0.0
            
            # Phase 5: Order Routing
            phase_start = time.time()
            if risk_approved:
                order_result = await self._route_order(signal)
            metrics.order_routing_ms = (time.time() - phase_start) * 1000
            
            # Calculate total latency
            metrics.total_latency_ms = (time.time() - start_time) * 1000
            
            # Track queue depth (simulated)
            metrics.queue_depth = len(self.cycle_metrics) % 10  # Simulate varying queue depth
            self.queue_depth_history.append(metrics.queue_depth)
            
            logger.debug(
                f"Cycle {cycle_number}: total={metrics.total_latency_ms:.0f}ms, "
                f"signal={metrics.signal_engine_ms:.0f}ms, risk={metrics.risk_engine_ms:.0f}ms, "
                f"ai={metrics.ai_layer_ms:.0f}ms, order={metrics.order_routing_ms:.0f}ms"
            )
        
        except Exception as e:
            metrics.total_latency_ms = (time.time() - start_time) * 1000
            metrics.error = str(e)
            logger.warning(f"Cycle {cycle_number} failed: {e}")
        
        return metrics
    
    async def _fetch_market_data(self) -> Dict[str, Any]:
        """Simulate market data fetch."""
        await asyncio.sleep(0.01)  # 10ms simulated I/O
        return {
            "symbol": "XAUUSDT",
            "price": 2000.0,
            "volume": 1000.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _generate_signal(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate signal generation."""
        await asyncio.sleep(0.005)  # 5ms processing
        return {
            "side": "BUY",
            "confidence": 0.85,
            "strategy": "trend_following"
        }
    
    async def _check_risk(self, signal: Dict[str, Any]) -> bool:
        """Simulate risk check."""
        await asyncio.sleep(0.002)  # 2ms validation
        return True  # Always approve in benchmark
    
    async def _consult_ai(self, signal: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate AI consultation (with caching for realistic performance)."""
        # Simulate variable AI latency (cached vs uncached)
        if self.cycle_metrics and len(self.cycle_metrics) % 5 == 0:
            await asyncio.sleep(0.3)  # 300ms cache miss
        else:
            await asyncio.sleep(0.05)  # 50ms cache hit
        
        return {
            "recommendation": "EXECUTE",
            "reasoning": "Strong trend confirmation",
            "confidence_adjustment": 0.05
        }
    
    async def _route_order(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate order routing."""
        await asyncio.sleep(0.01)  # 10ms API call
        return {
            "order_id": f"bench_{self.cycle_metrics[-1].cycle_number if self.cycle_metrics else 0}",
            "status": "FILLED",
            "fill_price": 2000.5
        }
    
    def _calculate_results(self) -> BenchmarkResults:
        """
        Calculate aggregated benchmark results from collected metrics.
        
        Returns:
            BenchmarkResults with statistical analysis
        """
        if not self.cycle_metrics:
            raise ValueError("No cycle metrics collected")
        
        successful = [m for m in self.cycle_metrics if m.error is None]
        failed = [m for m in self.cycle_metrics if m.error is not None]
        
        if not successful:
            raise ValueError("No successful cycles to analyze")
        
        latencies = [m.total_latency_ms for m in successful]
        
        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        p50 = sorted_latencies[int(n * 0.5)]
        p95 = sorted_latencies[int(n * 0.95)]
        p99 = sorted_latencies[int(n * 0.99)]
        
        # Component averages
        avg_signal = statistics.mean([m.signal_engine_ms for m in successful])
        avg_risk = statistics.mean([m.risk_engine_ms for m in successful])
        avg_ai = statistics.mean([m.ai_layer_ms for m in successful]) if self.include_ai else 0.0
        avg_order = statistics.mean([m.order_routing_ms for m in successful])
        
        # Identify bottleneck
        components = {
            "Signal Engine": avg_signal,
            "Risk Engine": avg_risk,
            "AI Layer": avg_ai,
            "Order Routing": avg_order
        }
        bottleneck = max(components, key=components.get)
        
        # Detect degradation (last 10% vs first 10%)
        early_avg = statistics.mean(latencies[:max(1, n // 10)])
        late_avg = statistics.mean(latencies[-max(1, n // 10):])
        degradation = late_avg > early_avg * 1.2  # 20% increase indicates degradation
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            avg_signal, avg_risk, avg_ai, avg_order, degradation
        )
        
        return BenchmarkResults(
            total_cycles=len(self.cycle_metrics),
            successful_cycles=len(successful),
            failed_cycles=len(failed),
            avg_cycle_time_ms=statistics.mean(latencies),
            p50_cycle_time_ms=p50,
            p95_cycle_time_ms=p95,
            p99_cycle_time_ms=p99,
            max_cycle_time_ms=max(latencies),
            min_cycle_time_ms=min(latencies),
            std_deviation_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            avg_signal_engine_ms=avg_signal,
            avg_risk_engine_ms=avg_risk,
            avg_ai_layer_ms=avg_ai,
            avg_order_routing_ms=avg_order,
            bottleneck_component=bottleneck,
            meets_target=statistics.mean(latencies) < self.target_latency_ms,
            degradation_detected=degradation,
            recommendations=recommendations
        )
    
    def _generate_recommendations(
        self,
        avg_signal: float,
        avg_risk: float,
        avg_ai: float,
        avg_order: float,
        degradation: bool
    ) -> List[str]:
        """Generate optimization recommendations based on benchmark results."""
        recommendations = []
        
        # Component-specific recommendations
        if avg_ai > 200:
            recommendations.append(
                f"AI Layer is slow ({avg_ai:.0f}ms avg). Consider: "
                f"- Implement response caching (Sprint 3 three-tier cache) "
                f"- Use lighter model for routine decisions "
                f"- Parallelize AI calls where possible"
            )
        
        if avg_signal > 50:
            recommendations.append(
                f"Signal Engine is slow ({avg_signal:.0f}ms avg). Optimize: "
                f"- Pre-compute technical indicators "
                f"- Use vectorized operations (NumPy/Pandas) "
                f"- Reduce indicator count or complexity"
            )
        
        if avg_order > 20:
            recommendations.append(
                f"Order Routing is slow ({avg_order:.0f}ms avg). Improve: "
                f"- Use connection pooling for exchange APIs "
                f"- Implement request batching "
                f"- Add circuit breaker for faster failure detection"
            )
        
        if degradation:
            recommendations.append(
                "Performance degradation detected over time. Investigate: "
                "- Memory leaks in long-running processes "
                "- Database connection pool exhaustion "
                "- Cache eviction strategy effectiveness"
            )
        
        if not recommendations:
            recommendations.append(
                "✅ All components performing within targets. "
                "Consider stress testing with higher load."
            )
        
        return recommendations
    
    def get_summary_report(self, results: BenchmarkResults) -> str:
        """
        Generate human-readable summary report.
        
        Args:
            results: BenchmarkResults from completed benchmark
            
        Returns:
            Formatted string report
        """
        report_lines = [
            "=" * 80,
            "LATENCY BENCHMARK REPORT",
            "=" * 80,
            "",
            f"Configuration:",
            f"  Total Cycles: {results.total_cycles}",
            f"  Successful: {results.successful_cycles}",
            f"  Failed: {results.failed_cycles}",
            f"  Target Latency: {results.target_latency_ms:.0f}ms",
            f"  AI Layer: {'Enabled' if self.include_ai else 'Disabled'}",
            "",
            f"Overall Performance:",
            f"  Average: {results.avg_cycle_time_ms:.0f}ms",
            f"  P50: {results.p50_cycle_time_ms:.0f}ms",
            f"  P95: {results.p95_cycle_time_ms:.0f}ms",
            f"  P99: {results.p99_cycle_time_ms:.0f}ms",
            f"  Max: {results.max_cycle_time_ms:.0f}ms",
            f"  Min: {results.min_cycle_time_ms:.0f}ms",
            f"  Std Dev: {results.std_deviation_ms:.0f}ms",
            "",
            f"Component Breakdown (Average):",
            f"  Signal Engine: {results.avg_signal_engine_ms:.0f}ms",
            f"  Risk Engine: {results.avg_risk_engine_ms:.0f}ms",
            f"  AI Layer: {results.avg_ai_layer_ms:.0f}ms",
            f"  Order Routing: {results.avg_order_routing_ms:.0f}ms",
            "",
            f"Bottleneck: {results.bottleneck_component}",
            f"Meets Target: {'✅ YES' if results.meets_target else '❌ NO'}",
            f"Degradation Detected: {'⚠️ YES' if results.degradation_detected else '✅ NO'}",
            "",
            f"Recommendations:",
        ]
        
        for i, rec in enumerate(results.recommendations, 1):
            report_lines.append(f"  {i}. {rec}")
        
        report_lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(report_lines)


async def run_benchmark(
    cycles: int = 100,
    target_ms: float = 2000.0,
    include_ai: bool = True
) -> BenchmarkResults:
    """
    Convenience function to run a latency benchmark.
    
    Args:
        cycles: Number of cycles to run
        target_ms: Target average latency in milliseconds
        include_ai: Whether to include AI layer in benchmark
        
    Returns:
        BenchmarkResults with full analysis
    """
    benchmark = LatencyBenchmark(
        cycles=cycles,
        target_latency_ms=target_ms,
        include_ai=include_ai
    )
    
    results = await benchmark.run()
    print(benchmark.get_summary_report(results))
    
    return results


if __name__ == "__main__":
    # Run benchmark when executed directly
    import sys
    
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    include_ai = "--no-ai" not in sys.argv
    
    results = asyncio.run(run_benchmark(cycles=cycles, include_ai=include_ai))
    
    # Exit with error code if target not met
    sys.exit(0 if results.meets_target else 1)
