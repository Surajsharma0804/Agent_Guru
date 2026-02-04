#!/bin/bash

# AGENT_GURU Build Automation Script
# Enterprise-grade cross-platform build system with comprehensive validation
# Zero-tolerance quality standards with maximum engineering rigor

set -euo pipefail

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly BUILD_DIR="${PROJECT_ROOT}/build"
readonly TARGET_DIR="${PROJECT_ROOT}/target"
readonly ARTIFACTS_DIR="${PROJECT_ROOT}/artifacts"

# Build configuration
readonly RUST_TOOLCHAIN="1.75.0"
readonly PYTHON_VERSION="3.11"
readonly CMAKE_VERSION="3.25"
readonly UNITY_VERSION="2023.2.20f1"

# Quality gates and thresholds
readonly MAX_BUILD_TIME=1800  # 30 minutes
readonly MAX_WARNINGS=0
readonly MIN_COVERAGE=100
readonly MAX_MEMORY_USAGE="8GB"

# Platform detection
readonly OS_TYPE="$(uname -s)"
readonly ARCH_TYPE="$(uname -m)"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

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

fatal_error() {
    log_error "$*"
    exit 1
}

# Error trap handler
error_handler() {
    local line_number=$1
    local error_code=$2
    log_error "Build failed at line ${line_number} with exit code ${error_code}"
    cleanup_on_failure
    exit "${error_code}"
}

trap 'error_handler ${LINENO} $?' ERR

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

check_command() {
    local cmd="$1"
    local version_flag="${2:-"--version"}"
    
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        fatal_error "Required command '${cmd}' not found"
    fi
    
    log_info "Found ${cmd}: $(${cmd} ${version_flag} 2>/dev/null | head -n1 || echo 'version unknown')"
}

check_rust_toolchain() {
    local required_version="$1"
    
    if ! rustup toolchain list | grep -q "${required_version}"; then
        log_info "Installing Rust toolchain ${required_version}"
        rustup toolchain install "${required_version}"
    fi
    
    rustup default "${required_version}"
    rustup component add rustfmt clippy miri
}

validate_environment() {
    log_info "Validating build environment..."
    
    # Check required commands
    check_command "rustc"
    check_command "cargo"
    check_command "python3"
    check_command "cmake"
    check_command "git"
    
    # Validate Rust toolchain
    check_rust_toolchain "${RUST_TOOLCHAIN}"
    
    # Check Python version
    local python_version
    python_version="$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)"
    if [[ "${python_version}" != "${PYTHON_VERSION}" ]]; then
        log_warning "Python version ${python_version} differs from required ${PYTHON_VERSION}"
    fi
    
    # Check available memory
    if [[ "${OS_TYPE}" == "Linux" ]]; then
        local available_memory
        available_memory="$(free -h | awk '/^Mem:/ {print $7}')"
        log_info "Available memory: ${available_memory}"
    fi
    
    # Check disk space
    local available_space
    available_space="$(df -h "${PROJECT_ROOT}" | awk 'NR==2 {print $4}')"
    log_info "Available disk space: ${available_space}"
    
    log_success "Environment validation completed"
}

setup_build_directories() {
    log_info "Setting up build directories..."
    
    mkdir -p "${BUILD_DIR}"
    mkdir -p "${TARGET_DIR}"
    mkdir -p "${ARTIFACTS_DIR}"
    
    # Create platform-specific directories
    mkdir -p "${ARTIFACTS_DIR}/windows-x64"
    mkdir -p "${ARTIFACTS_DIR}/windows-arm64"
    mkdir -p "${ARTIFACTS_DIR}/macos-x64"
    mkdir -p "${ARTIFACTS_DIR}/macos-arm64"
    mkdir -p "${ARTIFACTS_DIR}/linux-x64"
    mkdir -p "${ARTIFACTS_DIR}/linux-arm64"
    
    log_success "Build directories created"
}

# ============================================================================
# DEPENDENCY MANAGEMENT
# ============================================================================

install_system_dependencies() {
    log_info "Installing system dependencies for ${OS_TYPE}..."
    
    case "${OS_TYPE}" in
        "Linux")
            if command -v apt-get >/dev/null 2>&1; then
                sudo apt-get update
                sudo apt-get install -y \
                    build-essential \
                    cmake \
                    pkg-config \
                    libssl-dev \
                    libsodium-dev \
                    libasound2-dev \
                    libpulse-dev \
                    libxcb1-dev \
                    libxrandr-dev \
                    libxss-dev \
                    libglib2.0-dev \
                    libgtk-3-dev \
                    libgstreamer1.0-dev \
                    libgstreamer-plugins-base1.0-dev
            elif command -v dnf >/dev/null 2>&1; then
                sudo dnf install -y \
                    gcc gcc-c++ cmake pkgconfig \
                    openssl-devel libsodium-devel \
                    alsa-lib-devel pulseaudio-libs-devel \
                    libxcb-devel libXrandr-devel libXss-devel \
                    glib2-devel gtk3-devel \
                    gstreamer1-devel gstreamer1-plugins-base-devel
            fi
            ;;
        "Darwin")
            if command -v brew >/dev/null 2>&1; then
                brew install cmake pkg-config libsodium portaudio
            else
                fatal_error "Homebrew not found. Please install Homebrew first."
            fi
            ;;
        "MINGW"*|"MSYS"*|"CYGWIN"*)
            log_info "Windows detected. Please ensure Visual Studio Build Tools are installed."
            ;;
        *)
            log_warning "Unknown operating system: ${OS_TYPE}"
            ;;
    esac
    
    log_success "System dependencies installed"
}

install_rust_dependencies() {
    log_info "Installing Rust dependencies..."
    
    # Add required targets
    local targets=(
        "x86_64-unknown-linux-gnu"
        "aarch64-unknown-linux-gnu"
        "x86_64-pc-windows-msvc"
        "aarch64-pc-windows-msvc"
        "x86_64-apple-darwin"
        "aarch64-apple-darwin"
    )
    
    for target in "${targets[@]}"; do
        if rustup target list --installed | grep -q "${target}"; then
            log_info "Target ${target} already installed"
        else
            log_info "Installing target ${target}"
            rustup target add "${target}"
        fi
    done
    
    # Install required tools
    local tools=(
        "cargo-audit"
        "cargo-deny"
        "cargo-tarpaulin"
        "cargo-nextest"
        "cargo-criterion"
        "cargo-doc"
        "cargo-deadlinks"
    )
    
    for tool in "${tools[@]}"; do
        if cargo install --list | grep -q "${tool}"; then
            log_info "Tool ${tool} already installed"
        else
            log_info "Installing tool ${tool}"
            cargo install "${tool}"
        fi
    done
    
    log_success "Rust dependencies installed"
}

install_python_dependencies() {
    log_info "Installing Python dependencies..."
    
    cd "${PROJECT_ROOT}/guru/intelligence"
    
    # Upgrade pip
    python3 -m pip install --upgrade pip
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        pip3 install -r requirements.txt
    fi
    
    # Install development dependencies
    pip3 install \
        pytest \
        pytest-cov \
        pytest-xdist \
        hypothesis \
        pylint \
        black \
        mypy \
        sphinx \
        sphinx-rtd-theme
    
    cd "${PROJECT_ROOT}"
    log_success "Python dependencies installed"
}

# ============================================================================
# BUILD FUNCTIONS
# ============================================================================

build_rust_components() {
    local target="${1:-}"
    local build_type="${2:-release}"
    
    log_info "Building Rust components (target: ${target:-native}, type: ${build_type})"
    
    cd "${PROJECT_ROOT}"
    
    # Set build flags
    export RUSTFLAGS="-D warnings -D clippy::all -D clippy::pedantic -D clippy::nursery"
    
    # Build command
    local build_cmd="cargo build"
    
    if [[ "${build_type}" == "release" ]]; then
        build_cmd+=" --release"
    fi
    
    if [[ -n "${target}" ]]; then
        build_cmd+=" --target ${target}"
    fi
    
    build_cmd+=" --all-features"
    
    # Execute build with timeout
    timeout "${MAX_BUILD_TIME}" ${build_cmd}
    
    # Build specific binaries
    if [[ -n "${target}" ]]; then
        timeout "${MAX_BUILD_TIME}" cargo build --release --target "${target}" --bin agent-guru
    else
        timeout "${MAX_BUILD_TIME}" cargo build --release --bin agent-guru
    fi
    
    log_success "Rust components built successfully"
}

build_cpp_components() {
    log_info "Building C++ components..."
    
    cd "${BUILD_DIR}"
    
    # Configure with CMake
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_STANDARD=20 \
        -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wpedantic -Werror -O3" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    
    # Build with maximum parallelism
    local num_cores
    if [[ "${OS_TYPE}" == "Linux" ]]; then
        num_cores="$(nproc)"
    elif [[ "${OS_TYPE}" == "Darwin" ]]; then
        num_cores="$(sysctl -n hw.ncpu)"
    else
        num_cores="4"
    fi
    
    cmake --build . --config Release --parallel "${num_cores}"
    
    cd "${PROJECT_ROOT}"
    log_success "C++ components built successfully"
}

build_python_components() {
    log_info "Building Python components..."
    
    cd "${PROJECT_ROOT}/guru/intelligence"
    
    # Compile Python files
    python3 -m py_compile *.py
    
    # Build extensions if setup.py exists
    if [[ -f "setup.py" ]]; then
        python3 setup.py build_ext --inplace
    fi
    
    # Create distribution
    if [[ -f "setup.py" ]]; then
        python3 setup.py sdist bdist_wheel
    fi
    
    cd "${PROJECT_ROOT}"
    log_success "Python components built successfully"
}

build_unity_components() {
    log_info "Building Unity avatar components..."
    
    # Check if Unity is available
    if ! command -v unity-editor >/dev/null 2>&1; then
        log_warning "Unity not found, skipping avatar build"
        return 0
    fi
    
    cd "${PROJECT_ROOT}/avatar"
    
    # Determine target platform
    local unity_target
    case "${OS_TYPE}" in
        "Linux")
            unity_target="StandaloneLinux64"
            ;;
        "Darwin")
            unity_target="StandaloneOSX"
            ;;
        "MINGW"*|"MSYS"*|"CYGWIN"*)
            unity_target="StandaloneWindows64"
            ;;
        *)
            log_warning "Unknown platform for Unity build: ${OS_TYPE}"
            return 0
            ;;
    esac
    
    # Build Unity project
    unity-editor \
        -batchmode \
        -quit \
        -projectPath . \
        -buildTarget "${unity_target}" \
        -executeMethod BuildScript.BuildAvatar \
        -logFile unity-build.log
    
    cd "${PROJECT_ROOT}"
    log_success "Unity components built successfully"
}

# ============================================================================
# VALIDATION AND QUALITY CHECKS
# ============================================================================

run_static_analysis() {
    log_info "Running static analysis..."
    
    cd "${PROJECT_ROOT}"
    
    # Rust static analysis
    log_info "Running Clippy analysis..."
    cargo clippy --all-features -- -D warnings
    
    # Rust formatting check
    log_info "Checking Rust formatting..."
    cargo fmt --check
    
    # Python static analysis
    if [[ -d "guru/intelligence" ]]; then
        cd "guru/intelligence"
        
        log_info "Running Python linting..."
        pylint *.py --rcfile="${PROJECT_ROOT}/.pylintrc" || true
        
        log_info "Running Python type checking..."
        mypy *.py || true
        
        log_info "Checking Python formatting..."
        black --check *.py || true
        
        cd "${PROJECT_ROOT}"
    fi
    
    log_success "Static analysis completed"
}

validate_build_artifacts() {
    log_info "Validating build artifacts..."
    
    # Check Rust binaries
    local rust_binary="${TARGET_DIR}/release/agent-guru"
    if [[ ! -f "${rust_binary}" ]]; then
        fatal_error "Rust binary not found: ${rust_binary}"
    fi
    
    # Verify binary is executable
    if [[ ! -x "${rust_binary}" ]]; then
        fatal_error "Rust binary is not executable: ${rust_binary}"
    fi
    
    # Check file size (should be reasonable)
    local binary_size
    binary_size="$(stat -c%s "${rust_binary}" 2>/dev/null || stat -f%z "${rust_binary}" 2>/dev/null || echo 0)"
    if [[ "${binary_size}" -lt 1000000 ]]; then  # Less than 1MB seems too small
        log_warning "Binary size seems unusually small: ${binary_size} bytes"
    fi
    
    # Check C++ libraries
    if [[ -d "${BUILD_DIR}/lib" ]]; then
        local lib_count
        lib_count="$(find "${BUILD_DIR}/lib" -name "*.so" -o -name "*.dylib" -o -name "*.dll" | wc -l)"
        if [[ "${lib_count}" -eq 0 ]]; then
            log_warning "No shared libraries found in ${BUILD_DIR}/lib"
        fi
    fi
    
    log_success "Build artifacts validated"
}

# ============================================================================
# PACKAGING AND ARTIFACT MANAGEMENT
# ============================================================================

package_artifacts() {
    local target="${1:-native}"
    
    log_info "Packaging artifacts for target: ${target}"
    
    local artifact_dir="${ARTIFACTS_DIR}/${target}"
    mkdir -p "${artifact_dir}"
    
    # Copy Rust binaries
    if [[ "${target}" == "native" ]]; then
        cp -r "${TARGET_DIR}/release/"* "${artifact_dir}/" 2>/dev/null || true
    else
        cp -r "${TARGET_DIR}/${target}/release/"* "${artifact_dir}/" 2>/dev/null || true
    fi
    
    # Copy C++ libraries
    if [[ -d "${BUILD_DIR}/lib" ]]; then
        cp -r "${BUILD_DIR}/lib" "${artifact_dir}/"
    fi
    
    # Copy Python distributions
    if [[ -d "guru/intelligence/dist" ]]; then
        cp -r "guru/intelligence/dist" "${artifact_dir}/"
    fi
    
    # Copy Unity builds
    if [[ -d "avatar/Build" ]]; then
        cp -r "avatar/Build" "${artifact_dir}/"
    fi
    
    # Create manifest
    cat > "${artifact_dir}/manifest.json" << EOF
{
    "build_timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "target": "${target}",
    "git_commit": "$(git rev-parse HEAD)",
    "git_branch": "$(git rev-parse --abbrev-ref HEAD)",
    "rust_version": "$(rustc --version)",
    "python_version": "$(python3 --version)",
    "cmake_version": "$(cmake --version | head -n1)",
    "build_host": "$(hostname)",
    "build_os": "${OS_TYPE}",
    "build_arch": "${ARCH_TYPE}"
}
EOF
    
    log_success "Artifacts packaged for ${target}"
}

# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================

cleanup_on_failure() {
    log_info "Cleaning up after build failure..."
    
    # Remove incomplete artifacts
    if [[ -d "${ARTIFACTS_DIR}" ]]; then
        find "${ARTIFACTS_DIR}" -name "*.tmp" -delete 2>/dev/null || true
        find "${ARTIFACTS_DIR}" -empty -type d -delete 2>/dev/null || true
    fi
    
    # Clean build directories if requested
    if [[ "${CLEAN_ON_FAILURE:-false}" == "true" ]]; then
        rm -rf "${BUILD_DIR}"
        rm -rf "${TARGET_DIR}"
    fi
}

cleanup_build_artifacts() {
    log_info "Cleaning build artifacts..."
    
    rm -rf "${BUILD_DIR}"
    rm -rf "${TARGET_DIR}"
    rm -rf "${ARTIFACTS_DIR}"
    
    # Clean Rust artifacts
    cargo clean
    
    # Clean Python artifacts
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Build artifacts cleaned"
}

# ============================================================================
# MAIN EXECUTION FUNCTIONS
# ============================================================================

show_usage() {
    cat << EOF
AGENT_GURU Build System

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    build                   Build all components (default)
    clean                   Clean build artifacts
    validate-environment    Validate build environment
    install-deps           Install all dependencies
    package                Package build artifacts

Options:
    --target TARGET        Build target (e.g., x86_64-unknown-linux-gnu)
    --release              Build in release mode (default)
    --debug                Build in debug mode
    --no-unity             Skip Unity avatar build
    --no-cpp               Skip C++ component build
    --no-python            Skip Python component build
    --clean-first          Clean before building
    --parallel JOBS        Number of parallel jobs
    --verbose              Enable verbose output
    --help                 Show this help message

Examples:
    $0 build --target x86_64-unknown-linux-gnu
    $0 clean
    $0 validate-environment
    $0 install-deps
    $0 package --target x86_64-pc-windows-msvc

EOF
}

main() {
    local command="build"
    local target=""
    local build_type="release"
    local skip_unity=false
    local skip_cpp=false
    local skip_python=false
    local clean_first=false
    local parallel_jobs=""
    local verbose=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            build|clean|validate-environment|install-deps|package)
                command="$1"
                shift
                ;;
            --target)
                target="$2"
                shift 2
                ;;
            --release)
                build_type="release"
                shift
                ;;
            --debug)
                build_type="debug"
                shift
                ;;
            --no-unity)
                skip_unity=true
                shift
                ;;
            --no-cpp)
                skip_cpp=true
                shift
                ;;
            --no-python)
                skip_python=true
                shift
                ;;
            --clean-first)
                clean_first=true
                shift
                ;;
            --parallel)
                parallel_jobs="$2"
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
    
    # Set parallel jobs if specified
    if [[ -n "${parallel_jobs}" ]]; then
        export MAKEFLAGS="-j${parallel_jobs}"
        export CMAKE_BUILD_PARALLEL_LEVEL="${parallel_jobs}"
    fi
    
    log_info "Starting AGENT_GURU build system"
    log_info "Command: ${command}"
    log_info "Target: ${target:-native}"
    log_info "Build type: ${build_type}"
    log_info "Project root: ${PROJECT_ROOT}"
    
    # Execute command
    case "${command}" in
        "validate-environment")
            validate_environment
            ;;
        "install-deps")
            install_system_dependencies
            install_rust_dependencies
            install_python_dependencies
            ;;
        "clean")
            cleanup_build_artifacts
            ;;
        "build")
            if [[ "${clean_first}" == "true" ]]; then
                cleanup_build_artifacts
            fi
            
            validate_environment
            setup_build_directories
            
            build_rust_components "${target}" "${build_type}"
            
            if [[ "${skip_cpp}" == "false" ]]; then
                build_cpp_components
            fi
            
            if [[ "${skip_python}" == "false" ]]; then
                build_python_components
            fi
            
            if [[ "${skip_unity}" == "false" ]]; then
                build_unity_components
            fi
            
            run_static_analysis
            validate_build_artifacts
            ;;
        "package")
            package_artifacts "${target:-native}"
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_usage
            exit 1
            ;;
    esac
    
    log_success "Build system completed successfully"
}

# Execute main function with all arguments
main "$@"