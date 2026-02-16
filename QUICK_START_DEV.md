# Quick Start Guide for Developers

Get Agent Guru up and running in minutes!

## Prerequisites

- Python 3.10+ (3.11 recommended)
- Rust 1.75+ (for guru Rust components)
- NVIDIA GPU (optional, but recommended for 10-50x speedup)
- 16GB RAM minimum (32GB recommended)
- 10GB free disk space

## Step 1: Clone and Setup

```bash
# Navigate to project
cd Agent_Guru

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

## Step 2: Install Dependencies

### Option A: With GPU Support (Recommended)

```bash
# Install PyTorch with CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install other dependencies
pip install -r requirements.txt

# Verify GPU setup
python test_gpu.py
```

If GPU test fails, see [GPU_SETUP.md](GPU_SETUP.md) for detailed instructions.

### Option B: CPU Only

```bash
# Install PyTorch CPU version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies
pip install -r requirements-cpu.txt
```

## Step 3: Build Rust Components

```bash
# Build with GPU support (if available)
cargo build --release

# Or build without Whisper (CPU only)
cargo build --release --no-default-features --features std
```

## Step 4: Verify Installation

```bash
# Test Rust build
cargo test --release

# Test Python GPU (if applicable)
python test_gpu.py

# Run Agent Guru
cargo run --release
```

## Step 5: Start Development

### Read the Specifications

All specs are in `.kiro/specs/`:

1. **Start here**: `.kiro/specs/README.md`
2. **Verification**: `.kiro/specs/VERIFICATION_COMPLETE.md`
3. **First task**: `.kiro/specs/guru-complete-integration/tasks.md`

### Key Specifications

| Spec | Purpose | Tasks |
|------|---------|-------|
| guru-complete-integration | Overall integration | - |
| guru-speech-engine | Voice interface | 18 |
| guru-llm-runtime | LLM providers | 19 |
| guru-platform-integration | OS control | 21 |
| guru-deployment-system | Installers | 11 |
| guru-agent-orchestration | Multi-agent | 11 |

### Project Structure

```
Agent_Guru/
├── .kiro/specs/          # Complete specifications (READ FIRST)
├── guru/                 # Rust implementation
│   ├── agents/           # Multi-agent orchestration
│   ├── avatar/           # Avatar & emotion
│   ├── deployment/       # Deployment system
│   ├── llm/              # LLM runtime
│   ├── memory/           # Memory system
│   ├── platform/         # Platform integration
│   ├── policy/           # Policy engine
│   └── security/         # Security & crypto
├── guru_speech/          # Python speech engine
├── guru_vision/          # Python vision engine
├── guru_deployment/      # Python deployment tools
└── guru_face/            # Face recognition data
```

## Development Workflow

### 1. Choose a Task

Start with Task 1 from `guru-complete-integration`:
```bash
# Read the task
cat .kiro/specs/guru-complete-integration/tasks.md
```

### 2. Implement

Follow the task requirements and design:
- Read `requirements.md` for acceptance criteria
- Read `design.md` for architecture
- Implement in appropriate module

### 3. Test

```bash
# Run Rust tests
cargo test --release

# Run Python tests
pytest guru_speech/ -v
pytest guru_vision/ -v

# Run specific test
cargo test test_name --release
```

### 4. Verify

```bash
# Check Rust code
cargo clippy --all-targets --all-features

# Format Rust code
cargo fmt

# Check Python code
black guru_speech/ guru_vision/
flake8 guru_speech/ guru_vision/
mypy guru_speech/ guru_vision/
```

## Common Commands

### Rust Development

```bash
# Build
cargo build --release

# Test
cargo test --release

# Run
cargo run --release

# Check without building
cargo check

# Format code
cargo fmt

# Lint
cargo clippy

# Documentation
cargo doc --open
```

### Python Development

```bash
# Run tests
pytest -v

# With coverage
pytest --cov=guru_speech --cov=guru_vision --cov-report=html

# Format code
black .
isort .

# Lint
flake8 .
pylint guru_speech/ guru_vision/

# Type check
mypy guru_speech/ guru_vision/
```

## GPU Monitoring

While developing with GPU:

```bash
# Watch GPU usage
watch -n 1 nvidia-smi

# Or continuous monitoring
nvidia-smi dmon
```

## Troubleshooting

### Issue: Import errors in Python

```bash
# Reinstall in development mode
pip install -e .
```

### Issue: Rust build fails

```bash
# Clean and rebuild
cargo clean
cargo build --release
```

### Issue: GPU not detected

```bash
# Verify GPU
python test_gpu.py

# Check NVIDIA driver
nvidia-smi

# See GPU_SETUP.md for detailed troubleshooting
```

### Issue: Tests fail

```bash
# Run with verbose output
cargo test --release -- --nocapture
pytest -v -s

# Run single test
cargo test test_name --release -- --nocapture
pytest guru_speech/test_file.py::test_name -v -s
```

## Performance Tips

1. **Always use --release for Rust**: Debug builds are 10-100x slower
2. **Enable GPU**: 10-50x speedup for ML operations
3. **Use cargo check**: Faster than cargo build for quick validation
4. **Parallel tests**: `cargo test --release -- --test-threads=4`
5. **Cache dependencies**: First build is slow, subsequent builds are fast

## Next Steps

1. ✅ Complete setup (you're here!)
2. 📖 Read `.kiro/specs/README.md`
3. 📋 Review `.kiro/specs/guru-complete-integration/tasks.md`
4. 🚀 Start implementing Task 1
5. 🧪 Write tests as you go
6. 🔄 Iterate and improve

## Resources

- **Specifications**: `.kiro/specs/`
- **GPU Setup**: `GPU_SETUP.md`
- **Project Status**: `PROJECT_STATUS.md`
- **Cleanup Log**: `CLEANUP_LOG.md`
- **Main README**: `README.md`

## Getting Help

- Check specification files for detailed requirements
- Review design documents for architecture
- Look at existing code for patterns
- Run tests to understand expected behavior

---

Happy coding! 🚀

Last Updated: February 16, 2026
