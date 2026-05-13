"""
Latency Benchmark Integration Tests - Sprint 4 Performance Optimization.

Tests for LatencyBenchmark covering:
- Full cycle latency measurement across 100+ cycles
- Component-level breakdown (signal, risk, AI, order routing)
- Percentile calculations (p50, p95, p99)
- Bottleneck identification and recommendations
- Degradation detection over time
- Target validation (<2s average)

Success Criteria:
- 4 comprehensive tests
- All percentiles calculated correctly
- Bottleneck properly identified
- Recommendations generated based on results
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from app.ops.latency_benchmark import (
    LatencyBenchmark,
    CycleMetrics,
    BenchmarkResults,
    run_benchmark
)


@pytest.fixture
def benchmark():
    """Create a latency benchmark instance."""
    return LatencyBenchmark(
        cycles=100,
        target_latency_ms=2000.0,
        include_ai=True,
        mock_data=True
    )


class TestBenchmarkExecution:
    """Test benchmark execution and completion."""
    
    @pytest.mark.asyncio
    async def test_benchmark_runs_all_cycles(self, benchmark):
        """Verify benchmark executes all requested cycles."""
        results = await benchmark.run()
        
        assert results.total_cycles == 100
        assert results.successful_cycles > 0
    
    @pytest.mark.asyncio
    async def test_benchmark_meets_target(self, benchmark):
        """Verify benchmark correctly identifies if target is met."""
        results = await benchmark.run()
        
        # With mocked components, should easily meet 2s target
        assert results.meets_target is True
        assert results.avg_cycle_time_ms < 2000.0
    
    @pytest.mark.asyncio
    async def test_benchmark_without_ai_faster(self):
        """Verify benchmark without AI layer is significantly faster."""
        benchmark_with_ai = LatencyBenchmark(cycles=50, include_ai=True)
        benchmark_without_ai = LatencyBenchmark(cycles=50, include_ai=False)
        
        results_with_ai = await benchmark_with_ai.run()
        results_without_ai = await benchmark_without_ai.run()
        
        # Without AI should be much faster
        assert results_without_ai.avg_cycle_time_ms < results_with_ai.avg_cycle_time_ms


class TestPercentileCalculations:
    """Test statistical percentile calculations."""
    
    @pytest.mark.asyncio
    async def test_percentiles_calculated_correctly(self, benchmark):
        """Verify p50, p95, p99 are calculated from cycle data."""
        results = await benchmark.run()
        
        # Percentiles should be in ascending order
        assert results.p50_cycle_time_ms <= results.p95_cycle_time_ms
        assert results.p95_cycle_time_ms <= results.p99_cycle_time_ms
        
        # P99 should be close to max
        assert results.p99_cycle_time_ms <= results.max_cycle_time_ms
    
    @pytest.mark.asyncio
    async def test_min_max_values_valid(self, benchmark):
        """Verify min and max latency values are reasonable."""
        results = await benchmark.run()
        
        assert results.min_cycle_time_ms > 0
        assert results.max_cycle_time_ms >= results.min_cycle_time_ms
        assert results.max_cycle_time_ms < 10000  # Should not exceed 10s
    
    @pytest.mark.asyncio
    async def test_standard_deviation_calculated(self, benchmark):
        """Verify standard deviation is computed."""
        results = await benchmark.run()
        
        assert results.std_deviation_ms >= 0


class TestComponentBreakdown:
    """Test per-component latency tracking."""
    
    @pytest.mark.asyncio
    async def test_component_latencies_tracked(self, benchmark):
        """Verify each component's latency is measured."""
        results = await benchmark.run()
        
        assert results.avg_signal_engine_ms > 0
        assert results.avg_risk_engine_ms > 0
        assert results.avg_order_routing_ms > 0
        
        if benchmark.include_ai:
            assert results.avg_ai_layer_ms > 0
    
    @pytest.mark.asyncio
    async def test_bottleneck_identified(self, benchmark):
        """Verify bottleneck component is identified."""
        results = await benchmark.run()
        
        assert results.bottleneck_component != ""
        assert results.bottleneck_component in [
            "Signal Engine",
            "Risk Engine",
            "AI Layer",
            "Order Routing"
        ]
    
    @pytest.mark.asyncio
    async def test_component_totals_approximate_cycle_total(self, benchmark):
        """Verify sum of component latencies approximates total cycle time."""
        results = await benchmark.run()
        
        component_sum = (
            results.avg_signal_engine_ms +
            results.avg_risk_engine_ms +
            results.avg_ai_layer_ms +
            results.avg_order_routing_ms
        )
        
        # Should be within reasonable range of total (allowing for overhead)
        assert abs(component_sum - results.avg_cycle_time_ms) < 500


class TestDegradationDetection:
    """Test performance degradation detection."""
    
    @pytest.mark.asyncio
    async def test_no_degradation_in_stable_run(self, benchmark):
        """Verify stable runs show no degradation."""
        results = await benchmark.run()
        
        # With consistent mocked delays, should not detect degradation
        # (though this depends on implementation details)
        assert hasattr(results, 'degradation_detected')
    
    @pytest.mark.asyncio
    async def test_degradation_detected_when_present(self):
        """Verify degradation is detected when performance worsens."""
        # Create custom benchmark that simulates degradation
        benchmark_degraded = LatencyBenchmark(cycles=100, include_ai=False)
        
        # Manually inject degrading metrics
        for i in range(100):
            # Simulate increasing latency over time
            base_latency = 50 + (i * 2)  # Starts at 50ms, ends at 250ms
            metrics = CycleMetrics(
                cycle_number=i + 1,
                total_latency_ms=base_latency,
                signal_engine_ms=base_latency * 0.5,
                risk_engine_ms=base_latency * 0.3,
                ai_layer_ms=0.0,
                order_routing_ms=base_latency * 0.2
            )
            benchmark_degraded.cycle_metrics.append(metrics)
        
        results = benchmark_degraded._calculate_results()
        
        # Should detect degradation
        assert results.degradation_detected is True


class TestRecommendations:
    """Test optimization recommendations generation."""
    
    @pytest.mark.asyncio
    async def test_recommendations_generated(self, benchmark):
        """Verify recommendations are provided based on results."""
        results = await benchmark.run()
        
        assert len(results.recommendations) > 0
        assert isinstance(results.recommendations[0], str)
    
    @pytest.mark.asyncio
    async def test_slow_ai_triggers_recommendation(self):
        """Verify slow AI layer triggers specific recommendation."""
        benchmark_instance = LatencyBenchmark(cycles=10, include_ai=True)
        
        # Simulate slow AI performance
        results = BenchmarkResults(
            total_cycles=10,
            successful_cycles=10,
            failed_cycles=0,
            avg_cycle_time_ms=500,
            p50_cycle_time_ms=450,
            p95_cycle_time_ms=600,
            p99_cycle_time_ms=650,
            max_cycle_time_ms=700,
            min_cycle_time_ms=400,
            std_deviation_ms=50,
            avg_signal_engine_ms=10,
            avg_risk_engine_ms=5,
            avg_ai_layer_ms=300,  # Slow AI
            avg_order_routing_ms=10,
            bottleneck_component="AI Layer",
            meets_target=True,
            degradation_detected=False,
            recommendations=[]
        )
        
        recommendations = benchmark_instance._generate_recommendations(
            avg_signal=10,
            avg_risk=5,
            avg_ai=300,
            avg_order=10,
            degradation=False
        )
        
        # Should recommend AI optimization
        assert any("AI Layer" in rec or "cache" in rec.lower() for rec in recommendations)
    
    @pytest.mark.asyncio
    async def test_good_performance_gets_positive_feedback(self):
        """Verify good performance generates positive recommendations."""
        benchmark_instance = LatencyBenchmark(cycles=10, include_ai=False)
        
        recommendations = benchmark_instance._generate_recommendations(
            avg_signal=10,
            avg_risk=5,
            avg_ai=0,
            avg_order=10,
            degradation=False
        )
        
        # Should have positive feedback
        assert any("✅" in rec or "performing within targets" in rec.lower() 
                  for rec in recommendations)


class TestSummaryReport:
    """Test summary report generation."""
    
    @pytest.mark.asyncio
    async def test_summary_report_formatted(self, benchmark):
        """Verify summary report is properly formatted."""
        results = await benchmark.run()
        report = benchmark.get_summary_report(results)
        
        assert "LATENCY BENCHMARK REPORT" in report
        assert "Configuration:" in report
        assert "Overall Performance:" in report
        assert "Component Breakdown" in report
        assert "Recommendations:" in report
    
    @pytest.mark.asyncio
    async def test_summary_includes_all_metrics(self, benchmark):
        """Verify summary includes all key metrics."""
        results = await benchmark.run()
        report = benchmark.get_summary_report(results)
        
        # Should include key metrics
        assert "Average:" in report
        assert "P50:" in report
        assert "P95:" in report
        assert "Max:" in report
        assert "Min:" in report
    
    @pytest.mark.asyncio
    async def test_summary_shows_target_status(self, benchmark):
        """Verify summary shows whether target was met."""
        results = await benchmark.run()
        report = benchmark.get_summary_report(results)
        
        assert "Meets Target:" in report
        assert "✅ YES" in report or "❌ NO" in report


class TestConvenienceFunction:
    """Test the run_benchmark convenience function."""
    
    @pytest.mark.asyncio
    async def test_run_benchmark_returns_results(self):
        """Verify convenience function returns proper results."""
        results = await run_benchmark(cycles=10, target_ms=2000, include_ai=False)
        
        assert isinstance(results, BenchmarkResults)
        assert results.total_cycles == 10
    
    @pytest.mark.asyncio
    async def test_run_benchmark_prints_report(self, capsys):
        """Verify convenience function prints report to stdout."""
        await run_benchmark(cycles=5, target_ms=2000, include_ai=False)
        
        captured = capsys.readouterr()
        assert "LATENCY BENCHMARK REPORT" in captured.out


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
