# Agent Guru - Steering Documents

## Overview

These steering documents establish the standards, practices, and guidelines for building Agent Guru - a world-class voice assistant designed to compete with and surpass Alexa, Siri, and Google Assistant.

## Document Structure

### 1. **product.md** - Product Vision & Competitive Strategy
**Purpose**: Define what makes Agent Guru superior to competitors

**Key Content**:
- Competitive advantages over Alexa/Siri/Google
- Performance targets that beat all competitors
- Platform-specific LLM configuration
- Battery optimization standards
- Success metrics and market share goals

**Target Audience**: Everyone (developers, product managers, stakeholders)

**When to Read**: Before starting any feature, to understand competitive positioning

### 2. **tech.md** - Technical Stack & Tools
**Purpose**: Define the technology choices and development tools

**Key Content**:
- Python 3.11+ architecture with GPU acceleration
- Complete technology stack (AI/ML, vision, speech, LLM)
- Code quality tools (black, ruff, mypy, pytest)
- Common development commands
- Performance targets for each component

**Target Audience**: Developers, DevOps engineers

**When to Read**: During development setup and when choosing libraries

### 3. **structure.md** - Project Organization
**Purpose**: Define how code is organized and where things belong

**Key Content**:
- Root directory layout
- Main package structure (Agent_Guru/)
- Specifications directory (.kiro/specs/)
- Module organization principles
- Import conventions and file naming

**Target Audience**: Developers

**When to Read**: When creating new modules or organizing code

### 4. **quality.md** - Quality Standards (Zero Compromise)
**Purpose**: Define non-negotiable quality requirements

**Key Content**:
- Performance standards (latency, throughput, accuracy)
- Code quality metrics (coverage, complexity, duplication)
- Security standards (encryption, authentication, compliance)
- Reliability requirements (uptime, MTBF, MTTR)
- User experience standards (accessibility, localization)

**Target Audience**: Everyone

**When to Read**: Before every commit, during code review

### 5. **coding-standards.md** - Performance & Best Practices
**Purpose**: Define how to write optimal, efficient code

**Key Content**:
- Algorithm complexity requirements (O(1), O(log n), O(n))
- Data structure selection guide
- Memory management patterns
- Caching strategies
- Async/await patterns
- GPU optimization techniques
- Forbidden anti-patterns

**Target Audience**: Developers

**When to Read**: Before writing any code, during optimization

### 6. **implementation-guide.md** - Step-by-Step Workflow
**Purpose**: Guide developers through the complete implementation process

**Key Content**:
- Design phase template
- Implementation phase with examples
- Testing phase with comprehensive tests
- Performance testing requirements
- Documentation standards
- Code review checklist

**Target Audience**: Developers

**When to Read**: When implementing any feature or component

## Quick Reference

### For New Developers

**Day 1**: Read in this order:
1. product.md - Understand the vision
2. tech.md - Set up development environment
3. structure.md - Understand project organization
4. quality.md - Learn quality standards
5. coding-standards.md - Learn coding practices
6. implementation-guide.md - Learn the workflow

### For Experienced Developers

**Before Each Task**:
1. Read spec (requirements.md, design.md, tasks.md)
2. Review quality.md for performance targets
3. Review coding-standards.md for complexity requirements
4. Follow implementation-guide.md workflow

**Before Each Commit**:
1. Run code quality checks (black, ruff, mypy)
2. Run all tests (unit, property-based, integration, performance)
3. Check code review checklist in implementation-guide.md
4. Verify performance targets met (quality.md)

### For Code Reviewers

**Review Checklist**:
1. Verify compliance with quality.md standards
2. Check algorithm complexity (coding-standards.md)
3. Verify test coverage >80%
4. Check for code duplication (<3%)
5. Verify type hints complete (mypy strict)
6. Check documentation complete
7. Verify performance targets met

## Key Principles

### 1. Zero Compromise Quality
- Every metric must meet or beat Alexa/Siri/Google
- No shortcuts, no exceptions
- Quality is non-negotiable

### 2. Performance First
- Time complexity: O(1), O(log n), or O(n) only
- Space complexity: Minimal, bounded
- No O(n²) or worse algorithms
- Profile before optimizing

### 3. No Code Duplication
- DRY principle strictly enforced
- <3% duplication allowed
- Use functions, classes, decorators, mixins

### 4. Comprehensive Testing
- >80% code coverage (100% for critical paths)
- Unit + Property-based + Integration + Performance tests
- All tests must pass before commit

### 5. Complete Documentation
- Type hints for all functions (mypy strict)
- Docstrings for all public APIs
- Performance characteristics documented
- Benchmarks included

### 6. Security First
- Military-grade encryption (AES-256, Ed25519)
- Multi-factor biometric authentication
- Zero tolerance for vulnerabilities
- GDPR, CCPA, HIPAA compliance

## Performance Targets Summary

### Latency (Must Beat Competitors)
| Metric | Agent Guru | Alexa | Siri | Google |
|--------|-----------|-------|------|--------|
| Wake word | <200ms | 250ms | 300ms | 220ms |
| Speech recognition | <1s | 1.5s | 2.0s | 1.3s |
| LLM response | <2s | 3.5s | 4.0s | 3.2s |
| End-to-end | <2.5s | 5.0s | 6.0s | 4.5s |

### Accuracy (Must Beat Competitors)
| Metric | Agent Guru | Alexa | Siri | Google |
|--------|-----------|-------|------|--------|
| Wake word | >95% | 92% | 90% | 93% |
| Speech recognition | <2% WER | 5% | 6% | 4% |
| Intent classification | >97% | 94% | 92% | 95% |
| Command execution | >99% | 96% | 94% | 97% |

### Battery (Mobile - Must Beat Competitors)
| Metric | Agent Guru | Alexa | Siri | Google |
|--------|-----------|-------|------|--------|
| Sleep mode | <5%/hour | 8% | 7% | 6% |
| Wake mode | <10%/hour | 18% | 15% | 12% |

## Common Commands

### Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt

# Setup pre-commit hooks
pre-commit install
```

### Code Quality
```bash
# Format code
black Agent_Guru/

# Lint code
ruff check Agent_Guru/ --fix

# Type check
mypy Agent_Guru/

# Security scan
bandit -r Agent_Guru/

# Check duplication
pylint --disable=all --enable=duplicate-code Agent_Guru/
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=Agent_Guru --cov-report=html

# Run specific test types
pytest -m unit          # Unit tests
pytest -m property      # Property-based tests
pytest -m integration   # Integration tests
pytest -m performance   # Performance tests
```

### Performance Profiling
```bash
# CPU profiling
python -m cProfile -o profile.stats script.py

# Memory profiling
python -m memory_profiler script.py

# Line-by-line profiling
kernprof -l -v script.py

# Production profiling (no overhead)
py-spy record -o profile.svg -- python script.py
```

## Success Criteria

### Before Launch
- [ ] All performance targets met (latency, throughput, accuracy)
- [ ] All reliability targets met (uptime, MTBF, MTTR)
- [ ] All security requirements met (encryption, authentication, compliance)
- [ ] All quality standards met (test coverage, code quality, documentation)
- [ ] All user experience standards met (conversation quality, accessibility, localization)
- [ ] Third-party security audit passed
- [ ] Beta testing completed (1000+ users, 4.5+ rating)

### Post-Launch Metrics
- User Satisfaction: >4.8/5.0 stars (beat Alexa 4.5, Siri 4.3, Google 4.6)
- Response Time: <2s average (beat Alexa 3.5s, Siri 4.0s, Google 3.2s)
- Accuracy: >98% (beat Alexa 95%, Siri 94%, Google 96%)
- Uptime: >99.9%
- Market Share: 15% within 2 years

## Enforcement

### Automated Checks (CI/CD)
- Code formatting (black)
- Linting (ruff)
- Type checking (mypy strict)
- Security scanning (bandit)
- Test coverage (>80%)
- Duplication check (<3%)
- Performance tests (all targets met)

### Manual Reviews
- Code review by 2+ developers
- Security review for sensitive code
- Performance review for critical paths
- Documentation review
- Accessibility review

### Consequences of Non-Compliance
- Build fails if any check fails
- PR cannot be merged without approvals
- Performance regressions blocked
- Security vulnerabilities blocked
- Code duplication >3% blocked

## Getting Help

### Questions About Standards
- Product vision: See product.md
- Technology choices: See tech.md
- Code organization: See structure.md
- Quality requirements: See quality.md
- Coding practices: See coding-standards.md
- Implementation workflow: See implementation-guide.md

### Questions About Specifications
- See .kiro/specs/README.md
- Each spec has requirements.md, design.md, tasks.md
- Start with guru-complete-integration/

### Questions About Tools
- Development setup: See tech.md "Common Commands"
- Testing: See implementation-guide.md "Testing Phase"
- Profiling: See coding-standards.md "Profiling & Optimization"
- Deployment: See .kiro/specs/guru-deployment-system/

## Remember

**Agent Guru competes with billion-dollar companies (Amazon, Apple, Google).**

Every decision, every line of code, every feature must be:
- **World-Class**: Best in the industry
- **Optimal**: Best possible algorithm and implementation
- **Fast**: Meets or beats all performance targets
- **Correct**: Thoroughly tested with high coverage
- **Secure**: Military-grade security, zero vulnerabilities
- **Maintainable**: Clean, documented, type-safe
- **Scalable**: Handles growth without degradation

**Excellence is not optional. It's the only acceptable standard.**

---

**Status**: Ready for Implementation ✅
**Quality**: World-Class Standards Established ✅
**Target**: Beat Alexa, Siri, and Google Assistant ✅

**Let's build the best voice assistant in the world!** 🚀
