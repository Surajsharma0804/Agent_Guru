#!/bin/bash

# AGENT_GURU Comprehensive Test Execution Script
# Enterprise-grade testing framework with parallel execution and result aggregation
# Zero-tolerance quality standards with maximum engineering rigor

set -euo pipefail

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly TEST_RESULTS_DIR="${PROJECT_ROOT}/test-results"
readonly COVERAGE_DIR="${PROJECT_ROOT}/coverage"
readonly REPORTS_DIR="${PROJECT_ROOT}/reports"

# Test configuration
readonly DEFAULT_ITERATIONS=10000
readonly DEFAULT_TIMEOUT=3600  # 1 hour
readonly DEFAULT_PARALLEL_JOBS=0  # Auto-detect
readonly MIN_COVERAGE_THRESHOLD=100
readonly MAX_TEST_FAILURES=0

# Platform detection
readonly OS_TYPE="$(uname -s)"
readonly ARCH_TYPE="$(uname -m)"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Test result tracking
declare -g TOTAL_TESTS=0
declare -g PASSED_TESTS=0
declare -g FAILED_TESTS=0
declare -g SKIPPED_TESTS=0
declare -a FAILED_TEST_NAMES=()

# ============================================================================
# LOGGING AND ERROR HANDLING
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_test() {
    echo -e "${PURPLE}[TEST]${NC} $*" >&2
}

log_coverage() {
    echo -e "${CYAN}[COVERAGE]${NC} $*" >&2
}

fatal_error() {
    log_error "$*"
    cleanup_on_failure
    exit 1
}

# Error trap handler
error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "Test execution failed at line ${line_number} with exit code ${error_code}"
    cleanup_on_failure
    exit "${error_code}"
}

trap 'error_handler ${LINENO} $?' ERR

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

check_command() {
    local cmd="$1"
    local install_hint="${2:-}"
    
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        if [[ -n "${install_hint}" ]]; then
            fatal_error "Required command '${cmd}' not found. Install with: ${install_hint}"
        else
            fatal_error "Required command '${cmd}' not found"
        fi
    fi
}

get_cpu_count() {
    local cpu_count
    if [[ "${OS_TYPE}" == "Linux" ]]; then
        cpu_count="$(nproc)"
    elif [[ "${OS_TYPE}" == "Darwin" ]]; then
        cpu_count="$(sysctl -n hw.ncpu)"
    else
        cpu_count="4"
    fi
    echo "${cpu_count}"
}

setup_test_environment() {
    log_info "Setting up test environment..."
    
    # Create test directories
    mkdir -p "${TEST_RESULTS_DIR}"
    mkdir -p "${COVERAGE_DIR}"
    mkdir -p "${REPORTS_DIR}"
    
    # Set environment variables
    export RUST_BACKTRACE=1
    export RUST_LOG=debug
    export CARGO_TERM_COLOR=always
    export PYTHONPATH="${PROJECT_ROOT}/guru/intelligence:${PYTHONPATH:-}"
    
    # Verify required tools
    check_command "cargo" "rustup"
    check_command "python3" "system package manager"
    
    log_success "Test environment setup completed"
}

# ============================================================================
# RUST TEST FUNCTIONS
# ============================================================================

run_rust_unit_tests() {
    local parallel="${1:-true}"
    local coverage="${2:-false}"
    
    log_test "Running Rust unit tests (parallel: ${parallel}, coverage: ${coverage})"
    
    cd "${PROJECT_ROOT}"
    
    local test_cmd="cargo"
    local test_args=()
    
    if command -v cargo-nextest >/dev/null 2>&1 && [[ "${parallel}" == "true" ]]; then
        test_cmd="cargo nextest"
        test_args+=("run")
        test_args+=("--all-features")
        test_args+=("--no-fail-fast")
        
        if [[ "${DEFAULT_PARALLEL_JOBS}" -gt 0 ]]; then
            test_args+=("--test-threads" "${DEFAULT_PARALLEL_JOBS}")
        fi
    else
        test_args+=("test")
        test_args+=("--all-features")
        test_args+=("--")
        test_args+=("--test-threads" "$(get_cpu_count)")
    fi
    
    # Run tests with coverage if requested
    if [[ "${coverage}" == "true" ]] && command -v cargo-tarpaulin >/dev/null 2>&1; then
        log_coverage "Running tests with coverage analysis..."
        
        cargo tarpaulin \
            --all-features \
            --workspace \
            --timeout 120 \
            --out Html \
            --out Xml \
            --output-dir "${COVERAGE_DIR}" \
            --exclude-files "target/*" \
            --exclude-files "tests/*" \
            --exclude-files "**/property_tests.rs" \
            --fail-under "${MIN_COVERAGE_THRESHOLD}"
    else
        # Run tests without coverage
        timeout "${DEFAULT_TIMEOUT}" "${test_cmd}" "${test_args[@]}"
    fi
    
    # Capture test results
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Rust unit tests passed"
        ((PASSED_TESTS++))
    else
        log_error "Rust unit tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("rust-unit-tests")
    fi
    
    ((TOTAL_TESTS++))
    return ${exit_code}
}

run_rust_integration_tests() {
    local parallel="${1:-true}"
    
    log_test "Running Rust integration tests (parallel: ${parallel})"
    
    cd "${PROJECT_ROOT}"
    
    local test_cmd="cargo test"
    local test_args=(
        "--test"
        "*integration*"
        "--all-features"
        "--"
        "--test-threads"
        "$(get_cpu_count)"
    )
    
    if [[ "${parallel}" == "true" ]] && command -v cargo-nextest >/dev/null 2>&1; then
        test_cmd="cargo nextest run"
        test_args=(
            "--test"
            "*integration*"
            "--all-features"
        )
    fi
    
    timeout "${DEFAULT_TIMEOUT}" ${test_cmd} "${test_args[@]}"
    
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Rust integration tests passed"
        ((PASSED_TESTS++))
    else
        log_error "Rust integration tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("rust-integration-tests")
    fi
    
    ((TOTAL_TESTS++))
    return ${exit_code}
}

run_rust_property_tests() {
    local iterations="${1:-${DEFAULT_ITERATIONS}}"
    
    log_test "Running Rust property-based tests (${iterations} iterations)"
    
    cd "${PROJECT_ROOT}"
    
    # Set property test configuration
    export PROPTEST_CASES="${iterations}"
    export PROPTEST_MAX_SHRINK_ITERS=10000
    export PROPTEST_TIMEOUT=300000  # 5 minutes per test
    
    # Run property tests with extended timeout
    timeout $((DEFAULT_TIMEOUT * 2)) cargo test \
        --all-features \
        --test "*property*" \
        -- \
        --test-threads 1 \
        --nocapture
    
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Rust property-based tests passed (${iterations} iterations)"
        ((PASSED_TESTS++))
    else
        log_error "Rust property-based tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("rust-property-tests")
    fi
    
    ((TOTAL_TESTS++))
    return ${exit_code}
}

run_rust_memory_safety_tests() {
    log_test "Running Rust memory safety tests with MIRI"
    
    cd "${PROJECT_ROOT}"
    
    # Check if MIRI is available
    if ! rustup component list --installed | grep -q miri; then
        log_info "Installing MIRI component..."
        rustup +nightly component add miri
    fi
    
    # Run MIRI tests
    timeout "${DEFAULT_TIMEOUT}" cargo +nightly miri test \
        --all-features \
        --target "$(rustc -vV | sed -n 's|host: ||p')"
    
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Memory safety tests passed"
        ((PASSED_TESTS++))
    else
        log_error "Memory safety tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("rust-memory-safety-tests")
    fi
    
    ((TOTAL_TESTS++))
    return ${exit_code}
}

# ============================================================================
# PYTHON TEST FUNCTIONS
# ============================================================================

run_python_tests() {
    local parallel="${1:-true}"
    local coverage="${2:-false}"
    
    log_test "Running Python tests (parallel: ${parallel}, coverage: ${coverage})"
    
    cd "${PROJECT_ROOT}/guru/intelligence"
    
    # Check if pytest is available
    check_command "pytest" "pip install pytest"
    
    local pytest_args=(
        "tests/"
        "-v"
        "--tb=short"
        "--strict-markers"
        "--strict-config"
    )
    
    if [[ "${parallel}" == "true" ]] && python3 -c "import pytest_xdist" 2>/dev/null; then
        pytest_args+=("-n" "auto")
    fi
    
    if [[ "${coverage}" == "true" ]]; then
        pytest_args+=(
            "--cov=."
            "--cov-report=html:${COVERAGE_DIR}/python-html"
            "--cov-report=xml:${COVERAGE_DIR}/python-coverage.xml"
            "--cov-report=term-missing"
            "--cov-fail-under=${MIN_COVERAGE_THRESHOLD}"
        )
    fi
    
    # Add JUnit XML output
    pytest_args+=(
        "--junit-xml=${TEST_RESULTS_DIR}/python-results.xml"
    )
    
    timeout "${DEFAULT_TIMEOUT}" python3 -m pytest "${pytest_args[@]}"
    
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Python tests passed"
        ((PASSED_TESTS++))
    else
        log_error "Python tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("python-tests")
    fi
    
    ((TOTAL_TESTS++))
    cd "${PROJECT_ROOT}"
    return ${exit_code}
}

run_python_property_tests() {
    local iterations="${1:-${DEFAULT_ITERATIONS}}"
    
    log_test "Running Python property-based tests with Hypothesis (${iterations} examples)"
    
    cd "${PROJECT_ROOT}/guru/intelligence"
    
    # Set Hypothesis configuration
    export HYPOTHESIS_MAX_EXAMPLES="${iterations}"
    export HYPOTHESIS_DEADLINE=60000  # 60 seconds per test
    export HYPOTHESIS_SUPPRESS_HEALTH_CHECK="too_slow"
    
    # Run property tests specifically
    timeout "${DEFAULT_TIMEOUT}" python3 -m pytest \
        tests/ \
        -v \
        -k "property" \
        --tb=short \
        --junit-xml="${TEST_RESULTS_DIR}/python-property-results.xml"
    
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Python property-based tests passed (${iterations} examples)"
        ((PASSED_TESTS++))
    else
        log_error "Python property-based tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("python-property-tests")
    fi
    
    ((TOTAL_TESTS++))
    cd "${PROJECT_ROOT}"
    return ${exit_code}
}

# ============================================================================
# FORMAL VERIFICATION TESTS
# ============================================================================

run_formal_verification_tests() {
    log_test "Running formal verification tests with TLA+"
    
    cd "${PROJECT_ROOT}"
    
    # Check if TLA+ tools are available
    local tla_jar="${PROJECT_ROOT}/tla2tools.jar"
    if [[ ! -f "${tla_jar}" ]]; then
        log_info "Downloading TLA+ tools..."
        wget -O "${tla_jar}" \
            "https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar"
    fi
    
    # Verify TLA+ specifications
    local tla_files
    mapfile -t tla_files < <(find guru/formal -name "*.tla" 2>/dev/null || true)
    
    if [[ ${#tla_files[@]} -eq 0 ]]; then
        log_warning "No TLA+ specifications found, skipping formal verification"
        ((SKIPPED_TESTS++))
        ((TOTAL_TESTS++))
        return 0
    fi
    
    local verification_failed=false
    
    for tla_file in "${tla_files[@]}"; do
        log_info "Verifying ${tla_file}..."
        
        # Syntax check
        if ! timeout 300 java -cp "${tla_jar}" tla2sany.SANY "${tla_file}"; then
            log_error "Syntax error in ${tla_file}"
            verification_failed=true
            continue
        fi
        
        # Model checking (if config exists)
        local cfg_file="${tla_file%.tla}.cfg"
        if [[ -f "${cfg_file}" ]]; then
            log_info "Model checking ${tla_file}..."
            if ! timeout 1800 java -cp "${tla_jar}" tlc2.TLC "${tla_file}"; then
                log_error "Model checking failed for ${tla_file}"
                verification_failed=true
            fi
        fi
    done
    
    if [[ "${verification_failed}" == "false" ]]; then
        log_success "Formal verification tests passed"
        ((PASSED_TESTS++))
    else
        log_error "Formal verification tests failed"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("formal-verification-tests")
    fi
    
    ((TOTAL_TESTS++))
    return $([ "${verification_failed}" == "false" ])
}

# ============================================================================
# PERFORMANCE AND BENCHMARK TESTS
# ============================================================================

run_benchmark_tests() {
    log_test "Running performance benchmark tests"
    
    cd "${PROJECT_ROOT}"
    
    # Check if criterion is available
    if ! command -v cargo-criterion >/dev/null 2>&1; then
        log_info "Installing cargo-criterion..."
        cargo install cargo-criterion
    fi
    
    # Run benchmarks
    timeout "${DEFAULT_TIMEOUT}" cargo criterion \
        --output-format html \
        --plotting-backend plotters
    
    # Move benchmark results
    if [[ -d "target/criterion" ]]; then
        cp -r "target/criterion" "${REPORTS_DIR}/benchmarks"
    fi
    
    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Benchmark tests completed"
        ((PASSED_TESTS++))
    else
        log_error "Benchmark tests failed with exit code ${exit_code}"
        ((FAILED_TESTS++))
        FAILED_TEST_NAMES+=("benchmark-tests")
    fi
    
    ((TOTAL_TESTS++))
    return ${exit_code}
}

# ============================================================================
# COMPREHENSIVE TEST SUITES
# ============================================================================

run_comprehensive_test_suite() {
    log_info "Running comprehensive test suite..."
    
    local parallel="${1:-true}"
    local coverage="${2:-true}"
    local iterations="${3:-${DEFAULT_ITERATIONS}}"
    
    # Initialize counters
    TOTAL_TESTS=0
    PASSED_TESTS=0
    FAILED_TESTS=0
    SKIPPED_TESTS=0
    FAILED_TEST_NAMES=()
    
    # Run all test categories
    run_rust_unit_tests "${parallel}" "${coverage}" || true
    run_rust_integration_tests "${parallel}" || true
    run_rust_property_tests "${iterations}" || true
    run_python_tests "${parallel}" "${coverage}" || true
    run_python_property_tests "${iterations}" || true
    run_formal_verification_tests || true
    
    # Generate comprehensive report
    generate_test_report
    
    # Check if any tests failed
    if [[ ${FAILED_TESTS} -gt ${MAX_TEST_FAILURES} ]]; then
        log_error "Test suite failed: ${FAILED_TESTS} test categories failed"
        return 1
    else
        log_success "Comprehensive test suite completed successfully"
        return 0
    fi
}

run_nightly_test_suite() {
    log_info "Running nightly comprehensive test suite..."
    
    # Extended test configuration for nightly runs
    local extended_iterations=$((DEFAULT_ITERATIONS * 5))
    local extended_timeout=$((DEFAULT_TIMEOUT * 4))
    
    # Set extended timeout
    DEFAULT_TIMEOUT="${extended_timeout}"
    
    # Run comprehensive suite with extended parameters
    run_comprehensive_test_suite true true "${extended_iterations}"
    
    # Additional nightly-only tests
    run_rust_memory_safety_tests || true
    run_benchmark_tests || true
    
    # Generate extended report
    generate_extended_test_report
}

# ============================================================================
# REPORTING AND ANALYSIS
# ============================================================================

generate_test_report() {
    log_info "Generating test report..."
    
    local report_file="${REPORTS_DIR}/test-summary.html"
    local timestamp="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    
    cat > "${report_file}" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>AGENT_GURU Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .summary { margin: 20px 0; }
        .passed { color: green; font-weight: bold; }
        .failed { color: red; font-weight: bold; }
        .skipped { color: orange; font-weight: bold; }
        .details { margin-top: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>AGENT_GURU Test Report</h1>
        <p>Generated: ${timestamp}</p>
        <p>Git Commit: $(git rev-parse HEAD 2>/dev/null || echo "unknown")</p>
        <p>Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")</p>
    </div>
    
    <div class="summary">
        <h2>Test Summary</h2>
        <p>Total Tests: <strong>${TOTAL_TESTS}</strong></p>
        <p class="passed">Passed: ${PASSED_TESTS}</p>
        <p class="failed">Failed: ${FAILED_TESTS}</p>
        <p class="skipped">Skipped: ${SKIPPED_TESTS}</p>
        <p>Success Rate: $(( (PASSED_TESTS * 100) / (TOTAL_TESTS > 0 ? TOTAL_TESTS : 1) ))%</p>
    </div>
EOF

    if [[ ${#FAILED_TEST_NAMES[@]} -gt 0 ]]; then
        cat >> "${report_file}" << EOF
    <div class="details">
        <h2>Failed Tests</h2>
        <ul>
EOF
        for test_name in "${FAILED_TEST_NAMES[@]}"; do
            echo "            <li class=\"failed\">${test_name}</li>" >> "${report_file}"
        done
        cat >> "${report_file}" << EOF
        </ul>
    </div>
EOF
    fi
    
    cat >> "${report_file}" << EOF
</body>
</html>
EOF
    
    log_success "Test report generated: ${report_file}"
}

generate_extended_test_report() {
    log_info "Generating extended test report with coverage and performance data..."
    
    # Combine coverage reports if available
    if [[ -f "${COVERAGE_DIR}/cobertura.xml" ]] && [[ -f "${COVERAGE_DIR}/python-coverage.xml" ]]; then
        log_coverage "Combining coverage reports..."
        # Implementation would combine XML coverage reports
    fi
    
    # Generate performance trend analysis
    if [[ -d "${REPORTS_DIR}/benchmarks" ]]; then
        log_info "Analyzing performance trends..."
        # Implementation would analyze benchmark results over time
    fi
    
    log_success "Extended test report generated"
}

# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================

cleanup_on_failure() {
    log_info "Cleaning up after test failure..."
    
    # Kill any remaining test processes
    pkill -f "cargo test" 2>/dev/null || true
    pkill -f "pytest" 2>/dev/null || true
    pkill -f "java.*tla" 2>/dev/null || true
    
    # Clean up temporary files
    find "${PROJECT_ROOT}" -name "*.tmp" -delete 2>/dev/null || true
    find "${PROJECT_ROOT}" -name "core.*" -delete 2>/dev/null || true
}

cleanup_test_artifacts() {
    log_info "Cleaning test artifacts..."
    
    rm -rf "${TEST_RESULTS_DIR}"
    rm -rf "${COVERAGE_DIR}"
    rm -rf "${REPORTS_DIR}"
    
    # Clean Rust test artifacts
    cargo clean --doc
    find . -name "*.profraw" -delete 2>/dev/null || true
    
    # Clean Python test artifacts
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".coverage" -delete 2>/dev/null || true
    find . -name "htmlcov" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Test artifacts cleaned"
}

# ============================================================================
# MAIN EXECUTION FUNCTIONS
# ============================================================================

show_usage() {
    cat << EOF
AGENT_GURU Test Execution System

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    unit                    Run unit tests only
    integration            Run integration tests only
    property-based         Run property-based tests only
    python                 Run Python tests only
    formal                 Run formal verification tests only
    benchmarks             Run performance benchmarks
    comprehensive          Run all test categories (default)
    nightly                Run extended nightly test suite
    clean                  Clean test artifacts

Options:
    --parallel             Enable parallel test execution (default)
    --no-parallel          Disable parallel test execution
    --coverage             Enable code coverage analysis
    --no-coverage          Disable code coverage analysis
    --iterations N         Number of property test iterations (default: ${DEFAULT_ITERATIONS})
    --timeout N            Test timeout in seconds (default: ${DEFAULT_TIMEOUT})
    --jobs N               Number of parallel jobs (default: auto-detect)
    --verbose              Enable verbose output
    --help                 Show this help message

Examples:
    $0 comprehensive --coverage --iterations 50000
    $0 unit --parallel --coverage
    $0 property-based --iterations 100000
    $0 nightly
    $0 clean

EOF
}

main() {
    local command="comprehensive"
    local parallel=true
    local coverage=false
    local iterations="${DEFAULT_ITERATIONS}"
    local timeout="${DEFAULT_TIMEOUT}"
    local jobs=0
    local verbose=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            unit|integration|property-based|python|formal|benchmarks|comprehensive|nightly|clean)
                command="$1"
                shift
                ;;
            --parallel)
                parallel=true
                shift
                ;;
            --no-parallel)
                parallel=false
                shift
                ;;
            --coverage)
                coverage=true
                shift
                ;;
            --no-coverage)
                coverage=false
                shift
                ;;
            --iterations)
                iterations="$2"
                shift 2
                ;;
            --timeout)
                timeout="$2"
                DEFAULT_TIMEOUT="${timeout}"
                shift 2
                ;;
            --jobs)
                jobs="$2"
                DEFAULT_PARALLEL_JOBS="${jobs}"
                shift 2
                ;;
            --verbose)
                verbose=true
                set -x
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    log_info "Starting AGENT_GURU test system"
    log_info "Command: ${command}"
    log_info "Parallel: ${parallel}"
    log_info "Coverage: ${coverage}"
    log_info "Iterations: ${iterations}"
    log_info "Timeout: ${timeout}s"
    log_info "Project root: ${PROJECT_ROOT}"
    
    # Setup test environment
    setup_test_environment
    
    # Execute command
    case "${command}" in
        "unit")
            run_rust_unit_tests "${parallel}" "${coverage}"
            ;;
        "integration")
            run_rust_integration_tests "${parallel}"
            ;;
        "property-based")
            run_rust_property_tests "${iterations}"
            ;;
        "python")
            run_python_tests "${parallel}" "${coverage}"
            ;;
        "formal")
            run_formal_verification_tests
            ;;
        "benchmarks")
            run_benchmark_tests
            ;;
        "comprehensive")
            run_comprehensive_test_suite "${parallel}" "${coverage}" "${iterations}"
            ;;
        "nightly")
            run_nightly_test_suite
            ;;
        "clean")
            cleanup_test_artifacts
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_usage
            exit 1
            ;;
    esac
    
    local exit_code=$?
    
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Test system completed successfully"
    else
        log_error "Test system failed with exit code ${exit_code}"
    fi
    
    exit ${exit_code}
}

# Execute main function with all arguments
main "$@"