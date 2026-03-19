# Contributing to Agent Guru

## Code of Conduct

Be respectful, constructive, and collaborative. We're building world-class software together.

## How to Contribute

### Bug Reports
1. Check existing issues first
2. Include: OS, Python version, error message, steps to reproduce
3. Attach relevant log files from `.kiro/logs/`

### Feature Requests
1. Open an issue describing the feature and use case
2. Wait for discussion before implementing
3. Large features require a spec (requirements + design + tasks)

### Pull Requests
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Follow the development setup guide
4. Write tests (unit + property-based)
5. Ensure all checks pass: `pre-commit run --all-files`
6. Open PR with clear description

## Code Standards

### Must Pass
- `black Agent_Guru/ --line-length 100` - formatting
- `ruff check Agent_Guru/` - linting
- `mypy Agent_Guru/ --strict` - type checking
- `bandit -r Agent_Guru/ -ll` - security
- `pytest --cov=Agent_Guru --cov-fail-under=80` - 80%+ coverage

### Code Style
- Python 3.11+ type hints everywhere
- Google-style docstrings for all public APIs
- No O(n²) algorithms without justification
- No global mutable state
- Context managers for all resources

### Testing Requirements
- Unit tests for all functions
- Property-based tests for all correctness properties (Hypothesis, 100+ examples)
- Integration tests for component interactions
- Performance tests for latency-critical paths

## Review Process

1. Automated CI must pass (all checks green)
2. Two reviewer approvals required
3. Security review for any security-related changes
4. Performance review for latency-critical changes

## Commit Messages

Follow conventional commits:
```
feat: add wake word sensitivity setting
fix: resolve microphone reconnection race condition
test: add property tests for retry policy
docs: update architecture diagram
refactor: extract audio buffer to separate module
perf: optimize STT preprocessing pipeline
```
