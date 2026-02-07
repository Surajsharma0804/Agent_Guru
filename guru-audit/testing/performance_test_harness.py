"""
Performance Test Harness

Performance validation and benchmarking with timing constraint verification.
Implements comprehensive performance testing with statistical analysis.
"""

import time
import statistics
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional, Any
from enum import Enum


class PerformanceMetricType(Enum):
    """Performance metric types"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_UTILIZATION = "cpu_utilization"


@dataclass
class PerformanceConstraint:
    """Performance constraint specification"""
    metric_type: PerformanceMetricType
    threshold_value: float
    percentile: float = 99.9
    unit: str = "ms"


@dataclass
class PerformanceTestResult:
    """Performance test result"""
    test_name: str
    metric_type: PerformanceMetricType
    measurements: List[float]
    mean: float
    median: float
    std_dev: float
    min_value: float
    max_value: float
    percentile_99: float
    percentile_999: float
    constraint_met: bool
    duration_seconds: float


class PerformanceTestHarness:
    """
    Performance test harness with comprehensive benchmarking capabilities.
    
    Implements zero-tolerance performance validation with statistical analysis
    and timing constraint verification.
    """

    def __init__(self, constraints: List[PerformanceConstraint]):
        """
        Initialize performance test harness.
        
        Args:
            constraints: List of performance constraints to validate
        """
        self.constraints = constraints
        self.results: List[PerformanceTestResult] = []

    def execute_performance_tests(
        self,
        test_functions: Dict[str, Callable[[], Any]]
    ) -> List[PerformanceTestResult]:
        """
        Execute all performance tests.
        
        Args:
            test_functions: Dictionary of test name to test function
            
        Returns:
            List of performance test results
        """
        self.results = []

        for test_name, test_func in test_functions.items():
            result = self.execute_single_test(test_name, test_func)
            self.results.append(result)

        return self.results

    def execute_single_test(
        self,
        test_name: str,
        test_func: Callable[[], Any],
        iterations: int = 1000
    ) -> PerformanceTestResult:
        """
        Execute a single performance test.
        
        Args:
            test_name: Name of the test
            test_func: Test function to execute
            iterations: Number of iterations to run
            
        Returns:
            Performance test result
        """
        measurements: List[float] = []
        start_time = time.time()

        # Warm-up iterations
        for _ in range(min(10, iterations // 10)):
            test_func()

        # Measurement iterations
        for _ in range(iterations):
            iteration_start = time.perf_counter()
            test_func()
            iteration_end = time.perf_counter()
            
            # Convert to milliseconds
            duration_ms = (iteration_end - iteration_start) * 1000
            measurements.append(duration_ms)

        end_time = time.time()
        total_duration = end_time - start_time

        # Calculate statistics
        mean = statistics.mean(measurements)
        median = statistics.median(measurements)
        std_dev = statistics.stdev(measurements) if len(measurements) > 1 else 0.0
        min_value = min(measurements)
        max_value = max(measurements)
        
        sorted_measurements = sorted(measurements)
        percentile_99 = self._calculate_percentile(sorted_measurements, 99.0)
        percentile_999 = self._calculate_percentile(sorted_measurements, 99.9)

        # Check constraints
        constraint_met = self._check_constraints(
            test_name,
            PerformanceMetricType.LATENCY,
            percentile_999
        )

        return PerformanceTestResult(
            test_name=test_name,
            metric_type=PerformanceMetricType.LATENCY,
            measurements=measurements,
            mean=mean,
            median=median,
            std_dev=std_dev,
            min_value=min_value,
            max_value=max_value,
            percentile_99=percentile_99,
            percentile_999=percentile_999,
            constraint_met=constraint_met,
            duration_seconds=total_duration
        )

    def _calculate_percentile(self, sorted_values: List[float], percentile: float) -> float:
        """
        Calculate percentile value.
        
        Args:
            sorted_values: Sorted list of values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not sorted_values:
            return 0.0

        index = (percentile / 100.0) * (len(sorted_values) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)
        
        if lower_index == upper_index:
            return sorted_values[lower_index]
        
        # Linear interpolation
        fraction = index - lower_index
        return sorted_values[lower_index] * (1 - fraction) + sorted_values[upper_index] * fraction

    def _check_constraints(
        self,
        test_name: str,
        metric_type: PerformanceMetricType,
        value: float
    ) -> bool:
        """
        Check if performance constraints are met.
        
        Args:
            test_name: Name of the test
            metric_type: Type of metric
            value: Measured value
            
        Returns:
            True if constraints are met, False otherwise
        """
        for constraint in self.constraints:
            if constraint.metric_type == metric_type:
                if value > constraint.threshold_value:
                    return False
        return True

    def execute_throughput_test(
        self,
        test_name: str,
        test_func: Callable[[], Any],
        duration_seconds: float = 10.0
    ) -> PerformanceTestResult:
        """
        Execute throughput performance test.
        
        Args:
            test_name: Name of the test
            test_func: Test function to execute
            duration_seconds: Duration to run the test
            
        Returns:
            Performance test result
        """
        start_time = time.time()
        end_time = start_time + duration_seconds
        operations = 0
        measurements: List[float] = []

        while time.time() < end_time:
            iteration_start = time.perf_counter()
            test_func()
            iteration_end = time.perf_counter()
            
            operations += 1
            duration_ms = (iteration_end - iteration_start) * 1000
            measurements.append(duration_ms)

        total_duration = time.time() - start_time
        throughput = operations / total_duration

        # Calculate statistics
        mean = statistics.mean(measurements)
        median = statistics.median(measurements)
        std_dev = statistics.stdev(measurements) if len(measurements) > 1 else 0.0
        
        sorted_measurements = sorted(measurements)
        percentile_99 = self._calculate_percentile(sorted_measurements, 99.0)
        percentile_999 = self._calculate_percentile(sorted_measurements, 99.9)

        return PerformanceTestResult(
            test_name=test_name,
            metric_type=PerformanceMetricType.THROUGHPUT,
            measurements=measurements,
            mean=mean,
            median=median,
            std_dev=std_dev,
            min_value=min(measurements),
            max_value=max(measurements),
            percentile_99=percentile_99,
            percentile_999=percentile_999,
            constraint_met=True,
            duration_seconds=total_duration
        )

    def execute_memory_test(
        self,
        test_name: str,
        test_func: Callable[[], Any]
    ) -> PerformanceTestResult:
        """
        Execute memory usage performance test.
        
        Args:
            test_name: Name of the test
            test_func: Test function to execute
            
        Returns:
            Performance test result
        """
        import tracemalloc
        
        tracemalloc.start()
        start_time = time.time()
        
        # Execute test function
        test_func()
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Convert to MB
        current_mb = current / (1024 * 1024)
        peak_mb = peak / (1024 * 1024)

        return PerformanceTestResult(
            test_name=test_name,
            metric_type=PerformanceMetricType.MEMORY_USAGE,
            measurements=[current_mb, peak_mb],
            mean=current_mb,
            median=current_mb,
            std_dev=0.0,
            min_value=current_mb,
            max_value=peak_mb,
            percentile_99=peak_mb,
            percentile_999=peak_mb,
            constraint_met=self._check_constraints(
                test_name,
                PerformanceMetricType.MEMORY_USAGE,
                peak_mb
            ),
            duration_seconds=duration
        )

    def generate_report(self) -> str:
        """
        Generate performance test report.
        
        Returns:
            Formatted performance report
        """
        report = "=" * 80 + "\n"
        report += "PERFORMANCE TEST REPORT\n"
        report += "=" * 80 + "\n\n"

        for result in self.results:
            report += f"Test: {result.test_name}\n"
            report += f"Metric Type: {result.metric_type.value}\n"
            report += f"Mean: {result.mean:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"Median: {result.median:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"Std Dev: {result.std_dev:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"Min: {result.min_value:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"Max: {result.max_value:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"99th Percentile: {result.percentile_99:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"99.9th Percentile: {result.percentile_999:.2f} {self._get_unit(result.metric_type)}\n"
            report += f"Constraint Met: {'✓' if result.constraint_met else '✗'}\n"
            report += f"Duration: {result.duration_seconds:.2f} seconds\n"
            report += "-" * 80 + "\n\n"

        # Summary
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.constraint_met)
        failed_tests = total_tests - passed_tests

        report += "SUMMARY\n"
        report += f"Total Tests: {total_tests}\n"
        report += f"Passed: {passed_tests}\n"
        report += f"Failed: {failed_tests}\n"
        report += f"Pass Rate: {(passed_tests / total_tests * 100) if total_tests > 0 else 0:.2f}%\n"
        report += "=" * 80 + "\n"

        return report

    def _get_unit(self, metric_type: PerformanceMetricType) -> str:
        """Get unit for metric type"""
        units = {
            PerformanceMetricType.LATENCY: "ms",
            PerformanceMetricType.THROUGHPUT: "ops/sec",
            PerformanceMetricType.MEMORY_USAGE: "MB",
            PerformanceMetricType.CPU_UTILIZATION: "%",
        }
        return units.get(metric_type, "")

    def get_results(self) -> List[PerformanceTestResult]:
        """Get all test results"""
        return self.results

    def get_summary(self) -> Dict[str, Any]:
        """Get test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.constraint_met)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate
        }


# Example usage
if __name__ == "__main__":
    # Define performance constraints
    constraints = [
        PerformanceConstraint(
            metric_type=PerformanceMetricType.LATENCY,
            threshold_value=100.0,  # 100ms
            percentile=99.9,
            unit="ms"
        )
    ]

    # Create harness
    harness = PerformanceTestHarness(constraints)

    # Define test functions
    def test_function():
        time.sleep(0.001)  # Simulate 1ms operation

    # Execute tests
    test_functions = {
        "Test Operation": test_function
    }

    results = harness.execute_performance_tests(test_functions)

    # Generate report
    print(harness.generate_report())
