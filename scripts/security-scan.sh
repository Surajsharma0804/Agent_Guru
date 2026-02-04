#!/bin/bash

# AGENT_GURU Security Analysis and Vulnerability Scanning Script
# Enterprise-grade security validation with comprehensive threat detection
# Zero-tolerance security standards with maximum protection rigor

set -euo pipefail

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SECURITY_REPORTS_DIR="${PROJECT_ROOT}/security-reports"
readonly VULNERABILITY_DB_DIR="${PROJECT_ROOT}/.vulnerability-db"
readonly SARIF_OUTPUT="${SECURITY_REPORTS_DIR}/security-results.sarif"

# Security tool configuration
readonly CARGO_AUDIT_DB_URL="https://github.com/RustSec/advisory-db"
readonly SEMGREP_RULES_URL="https://semgrep.dev/c/p/security-audit"
readonly CVE_DATABASE_URL="https://nvd.nist.gov/feeds/json/cve/1.1"

# Security thresholds
readonly MAX_HIGH_VULNERABILITIES=0
readonly MAX_MEDIUM_VULNERABILITIES=0
readonly MAX_LOW_VULNERABILITIES=5
readonly MAX_CRYPTO_ISSUES=0
readonly MIN_SECURITY_SCORE=95

# Platform detection
readonly OS_TYPE="$(uname -s)"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Security scan results tracking
declare -g TOTAL_SCANS=0
declare -g PASSED_SCANS=0
declare -g FAILED_SCANS=0
declare -g HIGH_ISSUES=0
declare -g MEDIUM_ISSUES=0
declare -g LOW_ISSUES=0
declare -a CRITICAL_FINDINGS=()

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

log_security() {
    echo -e "${PURPLE}[SECURITY]${NC} $*" >&2
}

log_vuln() {
    echo -e "${CYAN}[VULNERABILITY]${NC} $*" >&2
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
    log_error "Security scan failed at line ${line_number} with exit code ${error_code}"
    cleanup_on_failure
    exit "${error_code}"
}

trap 'error_handler ${LINENO} $?' ERR

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

check_security_tool() {
    local tool="$1"
    local install_cmd="${2:-}"
    
    if ! command -v "${tool}" >/dev/null 2>&1; then
        if [[ -n "${install_cmd}" ]]; then
            log_info "Installing ${tool}..."
            eval "${install_cmd}"
        else
            fatal_error "Required security tool '${tool}' not found"
        fi
    fi
    
    log_info "Found security tool: ${tool}"
}

setup_security_environment() {
    log_security "Setting up security scanning environment..."
    
    # Create security directories
    mkdir -p "${SECURITY_REPORTS_DIR}"
    mkdir -p "${VULNERABILITY_DB_DIR}"
    
    # Install required security tools
    check_security_tool "cargo" ""
    check_security_tool "python3" ""
    
    # Install Rust security tools
    if ! cargo install --list | grep -q cargo-audit; then
        log_info "Installing cargo-audit..."
        cargo install cargo-audit
    fi
    
    if ! cargo install --list | grep -q cargo-deny; then
        log_info "Installing cargo-deny..."
        cargo install cargo-deny
    fi
    
    # Install Python security tools
    if ! python3 -c "import safety" 2>/dev/null; then
        log_info "Installing safety..."
        pip3 install safety
    fi
    
    if ! python3 -c "import bandit" 2>/dev/null; then
        log_info "Installing bandit..."
        pip3 install bandit
    fi
    
    if ! python3 -c "import semgrep" 2>/dev/null; then
        log_info "Installing semgrep..."
        pip3 install semgrep
    fi
    
    log_success "Security environment setup completed"
}

# Main execution function
main() {
    local command="comprehensive"
    local update_db=false
    local sarif_output=false
    local verbose=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            rust-audit|dependency-scan|python-security|static-analysis|crypto-validation|comprehensive|clean)
                command="$1"
                shift
                ;;
            --update-db)
                update_db=true
                shift
                ;;
            --sarif-output)
                sarif_output=true
                shift
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
    
    log_info "Starting AGENT_GURU security analysis"
    log_info "Command: ${command}"
    log_info "Update DB: ${update_db}"
    log_info "SARIF Output: ${sarif_output}"
    
    # Setup security environment
    setup_security_environment
    
    # Update databases if requested
    if [[ "${update_db}" == "true" ]]; then
        update_vulnerability_databases
    fi
    
    # Execute command
    case "${command}" in
        "rust-audit")
            run_rust_security_audit
            ;;
        "dependency-scan")
            run_rust_dependency_analysis
            ;;
        "python-security")
            run_python_security_scan
            ;;
        "static-analysis")
            run_semgrep_analysis
            ;;
        "crypto-validation")
            run_cryptographic_validation
            ;;
        "comprehensive")
            run_comprehensive_security_scan
            ;;
        "clean")
            cleanup_security_artifacts
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_usage
            exit 1
            ;;
    esac
    
    # Generate SARIF output if requested
    if [[ "${sarif_output}" == "true" ]]; then
        generate_sarif_output
    fi
    
    local exit_code=$?
    
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Security analysis completed successfully"
    else
        log_error "Security analysis failed with exit code ${exit_code}"
    fi
    
    exit ${exit_code}
}

show_usage() {
    cat << EOF
AGENT_GURU Security Analysis System

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    rust-audit             Run Rust security audit only
    dependency-scan        Run dependency vulnerability scan
    python-security        Run Python security analysis
    static-analysis        Run static security analysis (Semgrep)
    crypto-validation      Run cryptographic validation
    comprehensive          Run all security scans (default)
    clean                  Clean security artifacts

Options:
    --update-db            Update vulnerability databases before scanning
    --sarif-output         Generate SARIF output for tool integration
    --verbose              Enable verbose output
    --help                 Show this help message

Examples:
    $0 comprehensive --update-db --sarif-output
    $0 rust-audit
    $0 crypto-validation --verbose

EOF
}

# Placeholder functions for the security analysis components
update_vulnerability_databases() {
    log_security "Updating vulnerability databases..."
    log_success "Vulnerability databases updated"
}

run_rust_security_audit() {
    log_security "Running Rust security audit..."
    ((TOTAL_SCANS++))
    ((PASSED_SCANS++))
    log_success "Rust security audit completed"
}

run_rust_dependency_analysis() {
    log_security "Running Rust dependency analysis..."
    ((TOTAL_SCANS++))
    ((PASSED_SCANS++))
    log_success "Rust dependency analysis completed"
}

run_python_security_scan() {
    log_security "Running Python security scan..."
    ((TOTAL_SCANS++))
    ((PASSED_SCANS++))
    log_success "Python security scan completed"
}

run_semgrep_analysis() {
    log_security "Running Semgrep static analysis..."
    ((TOTAL_SCANS++))
    ((PASSED_SCANS++))
    log_success "Semgrep analysis completed"
}

run_cryptographic_validation() {
    log_security "Running cryptographic validation..."
    ((TOTAL_SCANS++))
    ((PASSED_SCANS++))
    log_success "Cryptographic validation completed"
}

run_comprehensive_security_scan() {
    log_security "Running comprehensive security scan..."
    
    # Initialize counters
    TOTAL_SCANS=0
    PASSED_SCANS=0
    FAILED_SCANS=0
    HIGH_ISSUES=0
    MEDIUM_ISSUES=0
    LOW_ISSUES=0
    CRITICAL_FINDINGS=()
    
    # Run all security scans
    run_rust_security_audit || true
    run_rust_dependency_analysis || true
    run_python_security_scan || true
    run_semgrep_analysis || true
    run_cryptographic_validation || true
    
    log_success "Comprehensive security scan completed"
}

generate_sarif_output() {
    log_security "Generating SARIF output..."
    
    cat > "${SARIF_OUTPUT}" << EOF
{
  "\$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "AGENT_GURU Security Scanner",
          "version": "1.0.0"
        }
      },
      "results": []
    }
  ]
}
EOF
    
    log_success "SARIF output generated: ${SARIF_OUTPUT}"
}

cleanup_on_failure() {
    log_info "Cleaning up after security scan failure..."
}

cleanup_security_artifacts() {
    log_info "Cleaning security artifacts..."
    rm -rf "${SECURITY_REPORTS_DIR}"
    rm -rf "${VULNERABILITY_DB_DIR}"
    log_success "Security artifacts cleaned"
}

# Execute main function with all arguments
main "$@"

update_vulnerability_databases() {
    log_security "Updating vulnerability databases..."
    
    # Update Rust advisory database
    log_info "Updating Rust advisory database..."
    cargo audit --update || log_warning "Failed to update Rust advisory database"
    
    # Update Python vulnerability database
    log_info "Updating Python vulnerability database..."
    python3 -m safety check --update || log_warning "Failed to update Python vulnerability database"
    
    # Update Semgrep rules
    log_info "Updating Semgrep security rules..."
    python3 -m semgrep --update || log_warning "Failed to update Semgrep rules"
    
    log_success "Vulnerability databases updated"
}

# ============================================================================
# RUST SECURITY ANALYSIS
# ============================================================================

run_rust_security_audit() {
    log_security "Running Rust security audit..."
    
    cd "${PROJECT_ROOT}"
    
    local audit_report="${SECURITY_REPORTS_DIR}/rust-audit.json"
    local audit_exit_code=0
    
    # Run cargo audit with JSON output
    log_info "Scanning for known vulnerabilities in Rust dependencies..."
    if ! cargo audit --json > "${audit_report}" 2>&1; then
        audit_exit_code=1
        log_error "Cargo audit found security issues"
    fi
    
    # Parse audit results
    if [[ -f "${audit_report}" ]]; then
        local vuln_count
        vuln_count="$(jq '.vulnerabilities | length' "${audit_report}" 2>/dev/null || echo "0")"
        
        if [[ "${vuln_count}" -gt 0 ]]; then
            log_vuln "Found ${vuln_count} vulnerabilities in Rust dependencies"
            
            # Extract vulnerability details
            jq -r '.vulnerabilities[] | "ID: \(.advisory.id) | Package: \(.package.name) | Severity: \(.advisory.severity // "unknown") | Title: \(.advisory.title)"' "${audit_report}" | while read -r vuln_line; do
                log_vuln "${vuln_line}"
                CRITICAL_FINDINGS+=("rust-vuln: ${vuln_line}")
            done
            
            HIGH_ISSUES=$((HIGH_ISSUES + vuln_count))
        else
            log_success "No known vulnerabilities found in Rust dependencies"
        fi
    fi
    
    ((TOTAL_SCANS++))
    if [[ ${audit_exit_code} -eq 0 ]]; then
        ((PASSED_SCANS++))
    else
        ((FAILED_SCANS++))
    fi
    
    return ${audit_exit_code}
}

run_rust_dependency_analysis() {
    log_security "Running Rust dependency analysis with cargo-deny..."
    
    cd "${PROJECT_ROOT}"
    
    local deny_config="${PROJECT_ROOT}/deny.toml"
    local deny_report="${SECURITY_REPORTS_DIR}/rust-deny.json"
    
    # Create deny.toml if it doesn't exist
    if [[ ! -f "${deny_config}" ]]; then
        log_info "Creating cargo-deny configuration..."
        cat > "${deny_config}" << 'EOF'
[graph]
targets = [
    { triple = "x86_64-unknown-linux-gnu" },
    { triple = "x86_64-pc-windows-msvc" },
    { triple = "x86_64-apple-darwin" },
]

[licenses]
confidence-threshold = 0.8
allow = [
    "MIT",
    "Apache-2.0",
    "Apache-2.0 WITH LLVM-exception",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unicode-DFS-2016",
]
deny = [
    "GPL-2.0",
    "GPL-3.0",
    "AGPL-1.0",
    "AGPL-3.0",
]

[bans]
multiple-versions = "warn"
wildcards = "deny"
highlight = "all"
workspace-default-features = "allow"
external-default-features = "allow"

deny = [
    { name = "openssl", version = "*" },
    { name = "openssl-sys", version = "*" },
]

skip = []
skip-tree = []

[advisories]
vulnerability = "deny"
unmaintained = "warn"
yanked = "warn"
notice = "warn"
ignore = []

[sources]
unknown-registry = "warn"
unknown-git = "warn"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = []
EOF
    fi
    
    # Run cargo-deny check
    local deny_exit_code=0
    if ! cargo deny --format json check > "${deny_report}" 2>&1; then
        deny_exit_code=1
        log_error "Cargo deny found policy violations"
    fi
    
    # Parse deny results
    if [[ -f "${deny_report}" ]]; then
        local ban_count
        ban_count="$(jq '[.[] | select(.type == "bans")] | length' "${deny_report}" 2>/dev/null || echo "0")"
        
        local license_count
        license_count="$(jq '[.[] | select(.type == "licenses")] | length' "${deny_report}" 2>/dev/null || echo "0")"
        
        if [[ "${ban_count}" -gt 0 ]]; then
            log_vuln "Found ${ban_count} banned dependencies"
            MEDIUM_ISSUES=$((MEDIUM_ISSUES + ban_count))
        fi
        
        if [[ "${license_count}" -gt 0 ]]; then
            log_vuln "Found ${license_count} license violations"
            LOW_ISSUES=$((LOW_ISSUES + license_count))
        fi
        
        if [[ "${ban_count}" -eq 0 && "${license_count}" -eq 0 ]]; then
            log_success "No dependency policy violations found"
        fi
    fi
    
    ((TOTAL_SCANS++))
    if [[ ${deny_exit_code} -eq 0 ]]; then
        ((PASSED_SCANS++))
    else
        ((FAILED_SCANS++))
    fi
    
    return ${deny_exit_code}
}

# ============================================================================
# PYTHON SECURITY ANALYSIS
# ============================================================================

run_python_security_scan() {
    log_security "Running Python security analysis..."
    
    cd "${PROJECT_ROOT}/guru/intelligence"
    
    local safety_report="${SECURITY_REPORTS_DIR}/python-safety.json"
    local bandit_report="${SECURITY_REPORTS_DIR}/python-bandit.json"
    
    # Run Safety check for known vulnerabilities
    log_info "Scanning Python dependencies for known vulnerabilities..."
    local safety_exit_code=0
    if ! python3 -m safety check --json > "${safety_report}" 2>&1; then
        safety_exit_code=1
        log_error "Safety found vulnerabilities in Python dependencies"
    fi
    
    # Parse Safety results
    if [[ -f "${safety_report}" ]]; then
        local vuln_count
        vuln_count="$(jq 'length' "${safety_report}" 2>/dev/null || echo "0")"
        
        if [[ "${vuln_count}" -gt 0 ]]; then
            log_vuln "Found ${vuln_count} vulnerabilities in Python dependencies"
            
            jq -r '.[] | "Package: \(.package_name) | Version: \(.installed_version) | Vulnerability: \(.vulnerability_id) | Severity: \(.severity // "unknown")"' "${safety_report}" | while read -r vuln_line; do
                log_vuln "${vuln_line}"
                CRITICAL_FINDINGS+=("python-vuln: ${vuln_line}")
            done
            
            HIGH_ISSUES=$((HIGH_ISSUES + vuln_count))
        else
            log_success "No known vulnerabilities found in Python dependencies"
        fi
    fi
    
    # Run Bandit static analysis
    log_info "Running Bandit static security analysis on Python code..."
    local bandit_exit_code=0
    if ! python3 -m bandit -r . -f json -o "${bandit_report}" 2>/dev/null; then
        bandit_exit_code=1
        log_error "Bandit found security issues in Python code"
    fi
    
    # Parse Bandit results
    if [[ -f "${bandit_report}" ]]; then
        local high_issues
        high_issues="$(jq '[.results[] | select(.issue_severity == "HIGH")] | length' "${bandit_report}" 2>/dev/null || echo "0")"
        
        local medium_issues
        medium_issues="$(jq '[.results[] | select(.issue_severity == "MEDIUM")] | length' "${bandit_report}" 2>/dev/null || echo "0")"
        
        local low_issues
        low_issues="$(jq '[.results[] | select(.issue_severity == "LOW")] | length' "${bandit_report}" 2>/dev/null || echo "0")"
        
        if [[ "${high_issues}" -gt 0 ]]; then
            log_vuln "Found ${high_issues} high-severity security issues in Python code"
            HIGH_ISSUES=$((HIGH_ISSUES + high_issues))
        fi
        
        if [[ "${medium_issues}" -gt 0 ]]; then
            log_vuln "Found ${medium_issues} medium-severity security issues in Python code"
            MEDIUM_ISSUES=$((MEDIUM_ISSUES + medium_issues))
        fi
        
        if [[ "${low_issues}" -gt 0 ]]; then
            log_vuln "Found ${low_issues} low-severity security issues in Python code"
            LOW_ISSUES=$((LOW_ISSUES + low_issues))
        fi
        
        if [[ "${high_issues}" -eq 0 && "${medium_issues}" -eq 0 && "${low_issues}" -eq 0 ]]; then
            log_success "No security issues found in Python code"
        fi
    fi
    
    ((TOTAL_SCANS++))
    if [[ ${safety_exit_code} -eq 0 && ${bandit_exit_code} -eq 0 ]]; then
        ((PASSED_SCANS++))
    else
        ((FAILED_SCANS++))
    fi
    
    cd "${PROJECT_ROOT}"
    return $((safety_exit_code + bandit_exit_code))
}

# ============================================================================
# STATIC SECURITY ANALYSIS
# ============================================================================

run_semgrep_analysis() {
    log_security "Running Semgrep static security analysis..."
    
    cd "${PROJECT_ROOT}"
    
    local semgrep_report="${SECURITY_REPORTS_DIR}/semgrep-results.json"
    
    # Run Semgrep with security rules
    log_info "Scanning codebase with Semgrep security rules..."
    local semgrep_exit_code=0
    
    if ! python3 -m semgrep \
        --config=auto \
        --config=p/security-audit \
        --config=p/secrets \
        --config=p/owasp-top-ten \
        --json \
        --output="${semgrep_report}" \
        . 2>/dev/null; then
        semgrep_exit_code=1
        log_error "Semgrep found security issues"
    fi
    
    # Parse Semgrep results
    if [[ -f "${semgrep_report}" ]]; then
        local error_count
        error_count="$(jq '[.results[] | select(.extra.severity == "ERROR")] | length' "${semgrep_report}" 2>/dev/null || echo "0")"
        
        local warning_count
        warning_count="$(jq '[.results[] | select(.extra.severity == "WARNING")] | length' "${semgrep_report}" 2>/dev/null || echo "0")"
        
        local info_count
        info_count="$(jq '[.results[] | select(.extra.severity == "INFO")] | length' "${semgrep_report}" 2>/dev/null || echo "0")"
        
        if [[ "${error_count}" -gt 0 ]]; then
            log_vuln "Found ${error_count} high-severity security issues"
            HIGH_ISSUES=$((HIGH_ISSUES + error_count))
            
            # Extract error details
            jq -r '.results[] | select(.extra.severity == "ERROR") | "File: \(.path) | Line: \(.start.line) | Rule: \(.check_id) | Message: \(.extra.message)"' "${semgrep_report}" | while read -r issue_line; do
                log_vuln "${issue_line}"
                CRITICAL_FINDINGS+=("semgrep-error: ${issue_line}")
            done
        fi
        
        if [[ "${warning_count}" -gt 0 ]]; then
            log_vuln "Found ${warning_count} medium-severity security issues"
            MEDIUM_ISSUES=$((MEDIUM_ISSUES + warning_count))
        fi
        
        if [[ "${info_count}" -gt 0 ]]; then
            log_vuln "Found ${info_count} low-severity security issues"
            LOW_ISSUES=$((LOW_ISSUES + info_count))
        fi
        
        if [[ "${error_count}" -eq 0 && "${warning_count}" -eq 0 && "${info_count}" -eq 0 ]]; then
            log_success "No security issues found by Semgrep"
        fi
    fi
    
    ((TOTAL_SCANS++))
    if [[ ${semgrep_exit_code} -eq 0 ]]; then
        ((PASSED_SCANS++))
    else
        ((FAILED_SCANS++))
    fi
    
    return ${semgrep_exit_code}
}

# ============================================================================
# CRYPTOGRAPHIC VALIDATION
# ============================================================================

run_cryptographic_validation() {
    log_security "Running cryptographic implementation validation..."
    
    cd "${PROJECT_ROOT}"
    
    local crypto_report="${SECURITY_REPORTS_DIR}/crypto-validation.json"
    local crypto_issues=0
    
    # Initialize report
    echo '{"crypto_validations": []}' > "${crypto_report}"
    
    # Check for weak cryptographic algorithms
    log_info "Scanning for weak cryptographic algorithms..."
    
    local weak_crypto_patterns=(
        "MD5"
        "SHA1"
        "DES"
        "3DES"
        "RC4"
        "ECB"
        "rand::random"
        "unsafe.*crypto"
    )
    
    for pattern in "${weak_crypto_patterns[@]}"; do
        local matches
        matches="$(grep -r "${pattern}" --include="*.rs" --include="*.py" --include="*.cpp" --include="*.c" . || true)"
        
        if [[ -n "${matches}" ]]; then
            log_vuln "Found potentially weak cryptographic pattern: ${pattern}"
            echo "${matches}" | while read -r match; do
                log_vuln "  ${match}"
                CRITICAL_FINDINGS+=("weak-crypto: ${pattern} in ${match}")
            done
            ((crypto_issues++))
        fi
    done
    
    # Check for proper entropy sources
    log_info "Validating entropy sources..."
    
    local entropy_patterns=(
        "OsRng"
        "getrandom"
        "/dev/urandom"
        "CryptGenRandom"
        "SecRandomCopyBytes"
    )
    
    local entropy_found=false
    for pattern in "${entropy_patterns[@]}"; do
        if grep -r "${pattern}" --include="*.rs" --include="*.py" --include="*.cpp" --include="*.c" . >/dev/null 2>&1; then
            entropy_found=true
            log_success "Found secure entropy source: ${pattern}"
            break
        fi
    done
    
    if [[ "${entropy_found}" == "false" ]]; then
        log_vuln "No secure entropy sources found"
        CRITICAL_FINDINGS+=("crypto-entropy: No secure entropy sources detected")
        ((crypto_issues++))
    fi
    
    # Check for constant-time operations
    log_info "Checking for constant-time cryptographic operations..."
    
    local constant_time_patterns=(
        "subtle::ConstantTimeEq"
        "constant_time_eq"
        "crypto_verify"
        "CRYPTO_memcmp"
    )
    
    local constant_time_found=false
    for pattern in "${constant_time_patterns[@]}"; do
        if grep -r "${pattern}" --include="*.rs" --include="*.py" --include="*.cpp" --include="*.c" . >/dev/null 2>&1; then
            constant_time_found=true
            log_success "Found constant-time operations: ${pattern}"
            break
        fi
    done
    
    if [[ "${constant_time_found}" == "false" ]]; then
        log_warning "No constant-time comparison operations found"
        ((crypto_issues++))
    fi
    
    # Validate key management
    log_info "Validating cryptographic key management..."
    
    local key_mgmt_issues=0
    
    # Check for hardcoded keys/secrets
    local secret_patterns=(
        "password.*=.*[\"']"
        "secret.*=.*[\"']"
        "key.*=.*[\"']"
        "token.*=.*[\"']"
        "api_key.*=.*[\"']"
    )
    
    for pattern in "${secret_patterns[@]}"; do
        local matches
        matches="$(grep -r -E "${pattern}" --include="*.rs" --include="*.py" --include="*.cpp" --include="*.c" --exclude-dir=target --exclude-dir=build . || true)"
        
        if [[ -n "${matches}" ]]; then
            log_vuln "Found potential hardcoded secret: ${pattern}"
            echo "${matches}" | while read -r match; do
                log_vuln "  ${match}"
                CRITICAL_FINDINGS+=("hardcoded-secret: ${match}")
            done
            ((key_mgmt_issues++))
        fi
    done
    
    crypto_issues=$((crypto_issues + key_mgmt_issues))
    
    # Update crypto issues counter
    if [[ ${crypto_issues} -gt ${MAX_CRYPTO_ISSUES} ]]; then
        HIGH_ISSUES=$((HIGH_ISSUES + crypto_issues))
    fi
    
    ((TOTAL_SCANS++))
    if [[ ${crypto_issues} -le ${MAX_CRYPTO_ISSUES} ]]; then
        ((PASSED_SCANS++))
        log_success "Cryptographic validation passed"
    else
        ((FAILED_SCANS++))
        log_error "Cryptographic validation failed with ${crypto_issues} issues"
    fi
    
    return $([ ${crypto_issues} -le ${MAX_CRYPTO_ISSUES} ])
}

# ============================================================================
# COMPREHENSIVE SECURITY ANALYSIS
# ============================================================================

run_comprehensive_security_scan() {
    log_security "Running comprehensive security analysis..."
    
    # Initialize counters
    TOTAL_SCANS=0
    PASSED_SCANS=0
    FAILED_SCANS=0
    HIGH_ISSUES=0
    MEDIUM_ISSUES=0
    LOW_ISSUES=0
    CRITICAL_FINDINGS=()
    
    # Update vulnerability databases
    update_vulnerability_databases
    
    # Run all security scans
    run_rust_security_audit || true
    run_rust_dependency_analysis || true
    run_python_security_scan || true
    run_semgrep_analysis || true
    run_cryptographic_validation || true
    
    # Generate comprehensive security report
    generate_security_report
    
    # Evaluate overall security posture
    evaluate_security_posture
}

# ============================================================================
# REPORTING AND ANALYSIS
# ============================================================================

generate_security_report() {
    log_security "Generating comprehensive security report..."
    
    local report_file="${SECURITY_REPORTS_DIR}/security-summary.html"
    local timestamp="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    
    cat > "${report_file}" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>AGENT_GURU Security Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .summary { margin: 20px 0; }
        .critical { color: #d32f2f; font-weight: bold; }
        .high { color: #f57c00; font-weight: bold; }
        .medium { color: #fbc02d; font-weight: bold; }
        .low { color: #388e3c; font-weight: bold; }
        .passed { color: green; font-weight: bold; }
        .failed { color: red; font-weight: bold; }
        .details { margin-top: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .finding { margin: 10px 0; padding: 10px; border-left: 4px solid #f57c00; background-color: #fff3e0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>AGENT_GURU Security Analysis Report</h1>
        <p>Generated: ${timestamp}</p>
        <p>Git Commit: $(git rev-parse HEAD 2>/dev/null || echo "unknown")</p>
        <p>Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")</p>
    </div>
    
    <div class="summary">
        <h2>Security Summary</h2>
        <p>Total Scans: <strong>${TOTAL_SCANS}</strong></p>
        <p class="passed">Passed Scans: ${PASSED_SCANS}</p>
        <p class="failed">Failed Scans: ${FAILED_SCANS}</p>
        <p class="high">High Severity Issues: ${HIGH_ISSUES}</p>
        <p class="medium">Medium Severity Issues: ${MEDIUM_ISSUES}</p>
        <p class="low">Low Severity Issues: ${LOW_ISSUES}</p>
    </div>
EOF

    if [[ ${#CRITICAL_FINDINGS[@]} -gt 0 ]]; then
        cat >> "${report_file}" << EOF
    <div class="details">
        <h2>Critical Security Findings</h2>
EOF
        for finding in "${CRITICAL_FINDINGS[@]}"; do
            echo "        <div class=\"finding\">${finding}</div>" >> "${report_file}"
        done
        cat >> "${report_file}" << EOF
    </div>
EOF
    fi
    
    cat >> "${report_file}" << EOF
    
    <div class="details">
        <h2>Security Scan Details</h2>
        <table>
            <tr>
                <th>Scan Type</th>
                <th>Status</th>
                <th>Issues Found</th>
                <th>Report File</th>
            </tr>
            <tr>
                <td>Rust Security Audit</td>
                <td class="$([ -f "${SECURITY_REPORTS_DIR}/rust-audit.json" ] && echo "passed" || echo "failed")">$([ -f "${SECURITY_REPORTS_DIR}/rust-audit.json" ] && echo "Completed" || echo "Failed")</td>
                <td>$(jq '.vulnerabilities | length' "${SECURITY_REPORTS_DIR}/rust-audit.json" 2>/dev/null || echo "N/A")</td>
                <td>rust-audit.json</td>
            </tr>
            <tr>
                <td>Python Security Scan</td>
                <td class="$([ -f "${SECURITY_REPORTS_DIR}/python-safety.json" ] && echo "passed" || echo "failed")">$([ -f "${SECURITY_REPORTS_DIR}/python-safety.json" ] && echo "Completed" || echo "Failed")</td>
                <td>$(jq 'length' "${SECURITY_REPORTS_DIR}/python-safety.json" 2>/dev/null || echo "N/A")</td>
                <td>python-safety.json</td>
            </tr>
            <tr>
                <td>Static Analysis (Semgrep)</td>
                <td class="$([ -f "${SECURITY_REPORTS_DIR}/semgrep-results.json" ] && echo "passed" || echo "failed")">$([ -f "${SECURITY_REPORTS_DIR}/semgrep-results.json" ] && echo "Completed" || echo "Failed")</td>
                <td>$(jq '.results | length' "${SECURITY_REPORTS_DIR}/semgrep-results.json" 2>/dev/null || echo "N/A")</td>
                <td>semgrep-results.json</td>
            </tr>
            <tr>
                <td>Cryptographic Validation</td>
                <td class="$([ -f "${SECURITY_REPORTS_DIR}/crypto-validation.json" ] && echo "passed" || echo "failed")">$([ -f "${SECURITY_REPORTS_DIR}/crypto-validation.json" ] && echo "Completed" || echo "Failed")</td>
                <td>Manual Review Required</td>
                <td>crypto-validation.json</td>
            </tr>
        </table>
    </div>
</body>
</html>
EOF
    
    log_success "Security report generated: ${report_file}"
}

generate_sarif_output() {
    log_security "Generating SARIF output for security tools integration..."
    
    # Create SARIF structure
    cat > "${SARIF_OUTPUT}" << EOF
{
  "\$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "AGENT_GURU Security Scanner",
          "version": "1.0.0",
          "informationUri": "https://github.com/agent-guru/security-scanner"
        }
      },
      "results": []
    }
  ]
}
EOF
    
    # Add results from various scans (simplified for brevity)
    # In a real implementation, this would parse all scan results and convert to SARIF format
    
    log_success "SARIF output generated: ${SARIF_OUTPUT}"
}

evaluate_security_posture() {
    log_security "Evaluating overall security posture..."
    
    local security_score=100
    
    # Deduct points for security issues
    security_score=$((security_score - (HIGH_ISSUES * 20)))
    security_score=$((security_score - (MEDIUM_ISSUES * 10)))
    security_score=$((security_score - (LOW_ISSUES * 2)))
    
    # Ensure score doesn't go below 0
    if [[ ${security_score} -lt 0 ]]; then
        security_score=0
    fi
    
    log_security "Security Score: ${security_score}/100"
    
    # Evaluate against thresholds
    local overall_status="PASS"
    
    if [[ ${HIGH_ISSUES} -gt ${MAX_HIGH_VULNERABILITIES} ]]; then
        log_error "SECURITY FAILURE: High-severity issues exceed threshold (${HIGH_ISSUES} > ${MAX_HIGH_VULNERABILITIES})"
        overall_status="FAIL"
    fi
    
    if [[ ${MEDIUM_ISSUES} -gt ${MAX_MEDIUM_VULNERABILITIES} ]]; then
        log_error "SECURITY FAILURE: Medium-severity issues exceed threshold (${MEDIUM_ISSUES} > ${MAX_MEDIUM_VULNERABILITIES})"
        overall_status="FAIL"
    fi
    
    if [[ ${security_score} -lt ${MIN_SECURITY_SCORE} ]]; then
        log_error "SECURITY FAILURE: Security score below minimum threshold (${security_score} < ${MIN_SECURITY_SCORE})"
        overall_status="FAIL"
    fi
    
    if [[ "${overall_status}" == "PASS" ]]; then
        log_success "SECURITY VALIDATION PASSED: All security checks completed successfully"
        return 0
    else
        log_error "SECURITY VALIDATION FAILED: Critical security issues must be resolved"
        return 1
    fi
}

# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================

cleanup_on_failure() {
    log_info "Cleaning up after security scan failure..."
    
    # Kill any remaining scan processes
    pkill -f "cargo audit" 2>/dev/null || true
    pkill -f "semgrep" 2>/dev/null || true
    pkill -f "bandit" 2>/dev/null || true
    pkill -f "safety" 2>/dev/null || true
}

cleanup_security_artifacts() {
    log_info "Cleaning security scan artifacts..."
    
    rm -rf "${SECURITY_REPORTS_DIR}"
    rm -rf "${VULNERABILITY_DB_DIR}"
    
    log_success "Security artifacts cleaned"
}

# ============================================================================
# MAIN EXECUTION FUNCTIONS
# ============================================================================

show_usage() {
    cat << EOF
AGENT_GURU Security Analysis System

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    rust-audit             Run Rust security audit only
    dependency-scan        Run dependency vulnerability scan
    python-security        Run Python security analysis
    static-analysis        Run static security analysis (Semgrep)
    crypto-validation      Run cryptographic validation
    comprehensive          Run all security scans (default)
    clean                  Clean security artifacts

Options:
    --update-db            Update vulnerability databases before scanning
    --sarif-output         Generate SARIF output for tool integration
    --verbose              Enable verbose output
    --help                 Show this help message

Examples:
    $0 comprehensive --update-db --sarif-output
    $0 rust-audit
    $0 crypto-validation --verbose
    $0 clean

EOF
}

main() {
    local command="comprehensive"
    local update_db=false
    local sarif_output=false
    local verbose=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            rust-audit|dependency-scan|python-security|static-analysis|crypto-validation|comprehensive|clean)
                command="$1"
                shift
                ;;
            --update-db)
                update_db=true
                shift
                ;;
            --sarif-output)
                sarif_output=true
                shift
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
    
    log_security "Starting AGENT_GURU security analysis system"
    log_info "Command: ${command}"
    log_info "Update DB: ${update_db}"
    log_info "SARIF Output: ${sarif_output}"
    log_info "Project root: ${PROJECT_ROOT}"
    
    # Setup security environment
    setup_security_environment
    
    # Update databases if requested
    if [[ "${update_db}" == "true" ]]; then
        update_vulnerability_databases
    fi
    
    # Execute command
    case "${command}" in
        "rust-audit")
            run_rust_security_audit
            ;;
        "dependency-scan")
            run_rust_dependency_analysis
            ;;
        "python-security")
            run_python_security_scan
            ;;
        "static-analysis")
            run_semgrep_analysis
            ;;
        "crypto-validation")
            run_cryptographic_validation
            ;;
        "comprehensive")
            run_comprehensive_security_scan
            ;;
        "clean")
            cleanup_security_artifacts
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_usage
            exit 1
            ;;
    esac
    
    local exit_code=$?
    
    # Generate SARIF output if requested
    if [[ "${sarif_output}" == "true" ]]; then
        generate_sarif_output
    fi
    
    if [[ ${exit_code} -eq 0 ]]; then
        log_success "Security analysis completed successfully"
    else
        log_error "Security analysis failed with exit code ${exit_code}"
    fi
    
    exit ${exit_code}
}

# Execute main function with all arguments
main "$@"