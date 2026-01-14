# GURU Git Workflow Guide

## Overview

This document defines the **mandatory Git workflow** for GURU development. Every task and sub-task completion MUST be committed and pushed before proceeding.

## Core Principles

1. **Atomic Commits**: Each task/sub-task = one commit
2. **Incremental Progress**: Commit after every meaningful change
3. **Rollback Safety**: Every commit is a rollback point
4. **Traceability**: Commits map directly to requirements and properties
5. **Quality Gates**: CI/CD validates every push

## Workflow Steps

### After EVERY Task/Sub-Task Completion

```bash
# 1. Check status
git status

# 2. Stage changes
git add .
# OR stage specific files
git add src/pal/interfaces.py src/pal/windows_backend.py

# 3. Commit with descriptive message
git commit -m "[Task X.Y] Brief description

- Detailed change 1
- Detailed change 2
- Requirements validated: X.Y, X.Z
- Properties tested: N, M

Validates: Requirements X.Y, X.Z
Tests: Property N, Property M"

# 4. Push to remote
git push origin feature/task-name

# 5. Verify push success
# Check for errors, CI/CD status

# 6. ONLY THEN proceed to next task
```

## Commit Message Format

### Structure

```
[Task X.Y] Brief description (50 chars max)
<blank line>
- Detailed change 1
- Detailed change 2
- Detailed change 3
<blank line>
Validates: Requirements X.Y, X.Z
Tests: Property N, Property M
```

### Examples

#### Task Completion
```
[Task 1.1] Create PAL interface definitions

- Defined Application_Controller abstract interface
- Defined Input_Automation abstract interface
- Defined Speech_Output abstract interface
- Defined Speech_Input abstract interface
- Defined Biometric_Authenticator abstract interface
- Defined Security_Enforcer abstract interface

Validates: Requirements 33.1, 34.1-34.4, 35.1-35.3, 36.1, 37.1-37.3, 38.1, 40.1
```

#### Sub-Task with Tests
```
[Task 1.3] Write property tests for PAL interfaces

- Property 94: Core Logic Platform Isolation
- Property 95: PAL Interface Communication
- Property 96: Application Controller Consistency
- Property 97: Input Automation Capability Declaration
- Property 112: Core Logic Platform-Agnostic Testing

All tests passing with 100+ iterations each.

Validates: Requirements 33.1, 33.2, 34.9, 35.8, 42.1, 42.2, 42.6
Tests: Property 94, 95, 96, 97, 112
```

#### Bug Fix
```
[Task 8.1] Implement wake word stripping algorithm

- Added wake word removal function to voice interface
- Strip "hey guru", "hello guru", "hi guru" (case-insensitive)
- Ensure stripped text is passed to all downstream systems
- Fixed bug where wake word interfered with command parsing

Validates: Requirements 30.1, 30.2, 30.3, 30.4, 30.5
Fixes: Issue #42 - Wake word interference
```

## Branch Strategy

### Branch Hierarchy

```
main (protected)
├── develop (integration branch)
│   ├── feature/pal-foundation (Task 1)
│   ├── feature/core-refactoring (Task 2)
│   ├── feature/authority-scope (Task 3)
│   ├── feature/macos-backend (Task 4)
│   ├── feature/android-backend (Task 5)
│   ├── feature/ios-backend (Task 6)
│   ├── feature/voice-fixes (Task 8)
│   ├── feature/response-ownership (Task 9)
│   └── ... (remaining features)
```

### Branch Naming Convention

```
feature/<task-name>       # New features
bugfix/<issue-description> # Bug fixes
hotfix/<critical-fix>     # Production hotfixes
refactor/<component-name> # Code refactoring
test/<test-type>          # Test additions
docs/<documentation>      # Documentation updates
```

### Branch Workflow

#### Starting a New Task

```bash
# Ensure you're on develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/pal-foundation

# Work on task...
# Complete sub-task 1.1
git add .
git commit -m "[Task 1.1] Create PAL interface definitions..."
git push origin feature/pal-foundation

# Complete sub-task 1.2
git add .
git commit -m "[Task 1.2] Implement Windows backend..."
git push origin feature/pal-foundation

# ... complete all sub-tasks ...

# All sub-tasks done, merge to develop
git checkout develop
git pull origin develop
git merge feature/pal-foundation
git push origin develop
```

#### Merging to Main (Production)

```bash
# After all tests pass on develop
git checkout main
git pull origin main
git merge develop
git push origin main

# Tag release
git tag -a v1.0.0 -m "Release v1.0.0: Cross-platform PAL implementation"
git push origin v1.0.0
```

## CI/CD Integration

### Automated Checks on Every Push

1. **Unit Tests**: All unit tests must pass
2. **Property Tests**: All property tests must pass (100+ iterations)
3. **Integration Tests**: Critical path tests must pass
4. **Security Scans**: No vulnerabilities allowed
5. **Code Coverage**: Must be ≥ 85%
6. **Linting**: No linting errors
7. **Type Checking**: No type errors (Python mypy, TypeScript tsc)
8. **Build Verification**: Must build successfully on all platforms

### Push Rejection Scenarios

Push will be **rejected** if:

```
❌ Tests fail (unit, property, integration)
❌ Security vulnerabilities detected
❌ Code coverage drops below 85%
❌ Linting errors present
❌ Type checking errors
❌ Build fails on any platform
❌ Property tests < 100 iterations
❌ Commit message format invalid
```

### CI/CD Pipeline Stages

```
Stage 1: Pre-commit Hooks (Local)
├── Linting (ESLint, Black, Flake8)
├── Type checking (mypy, tsc)
└── Unit tests (fast tests only)

Stage 2: Push Validation (Remote)
├── Full test suite (unit + property + integration)
├── Security scans (npm audit, safety, semgrep)
├── Code coverage analysis
└── Build verification (all platforms)

Stage 3: Merge Validation (Develop/Main)
├── Full regression tests
├── Performance benchmarks
├── Cross-platform testing
└── Documentation generation

Stage 4: Release (Main only)
├── Production build
├── Security audit
├── Deployment preparation
└── Release notes generation
```

## Rollback Procedures

### View Commit History

```bash
# View commit log
git log --oneline

# View detailed log
git log --graph --decorate --all

# View changes in specific commit
git show <commit-hash>
```

### Rollback to Previous Commit

```bash
# Rollback and keep changes (soft reset)
git reset --soft HEAD~1

# Rollback and discard changes (hard reset)
git reset --hard HEAD~1

# Rollback to specific commit
git reset --hard <commit-hash>

# Push force (use with caution!)
git push origin feature/task-name --force
```

### Revert Specific Commit

```bash
# Create new commit that undoes changes
git revert <commit-hash>
git push origin feature/task-name
```

### Emergency Rollback (Production)

```bash
# Rollback main to previous release
git checkout main
git reset --hard <previous-release-tag>
git push origin main --force

# Notify team immediately
# Create incident report
# Investigate root cause
```

## Quality Gates

### Before Proceeding to Next Task

Verify:
- ✅ All sub-tasks completed
- ✅ All tests passing (unit + property + integration)
- ✅ Code coverage ≥ 85%
- ✅ No security vulnerabilities
- ✅ All changes committed and pushed
- ✅ CI/CD pipeline green
- ✅ Code review approved (for develop/main merges)

### Checkpoint Requirements (Tasks 7, 13, 16, 29)

At each checkpoint:
1. Run full test suite
2. Verify all properties pass
3. Check code coverage ≥ 85%
4. Run security scans
5. Test on all available platforms
6. Review audit logs for integrity
7. Verify performance metrics
8. **Ask user for approval before proceeding**

## Best Practices

### Do's ✅

- ✅ Commit after every task/sub-task
- ✅ Write descriptive commit messages
- ✅ Reference requirements and properties
- ✅ Push immediately after commit
- ✅ Verify CI/CD status before proceeding
- ✅ Use feature branches for major tasks
- ✅ Merge to develop regularly
- ✅ Tag releases on main
- ✅ Keep commits atomic (one logical change)
- ✅ Test before committing

### Don'ts ❌

- ❌ Don't commit broken code
- ❌ Don't skip tests
- ❌ Don't push without verifying
- ❌ Don't commit sensitive data (keys, passwords)
- ❌ Don't force push to main/develop
- ❌ Don't commit large binary files
- ❌ Don't use vague commit messages
- ❌ Don't skip code review for main merges
- ❌ Don't proceed with failing CI/CD
- ❌ Don't commit commented-out code

## Git Configuration

### Required Git Config

```bash
# Set user identity
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Set default editor
git config --global core.editor "code --wait"

# Enable color output
git config --global color.ui auto

# Set default branch name
git config --global init.defaultBranch main

# Enable rebase on pull
git config --global pull.rebase true

# Enable auto-stash
git config --global rebase.autoStash true
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
# Install husky
npm install --save-dev husky

# Setup hooks
npm run setup:hooks

# Hooks will run automatically on commit
```

Pre-commit hooks run:
- Linting (ESLint, Black, Flake8)
- Type checking (mypy, tsc)
- Fast unit tests
- Commit message validation

## Troubleshooting

### Push Rejected

```bash
# Pull latest changes
git pull origin feature/task-name

# Resolve conflicts if any
# Then push again
git push origin feature/task-name
```

### Merge Conflicts

```bash
# View conflicts
git status

# Edit conflicted files
# Remove conflict markers (<<<<, ====, >>>>)

# Stage resolved files
git add <resolved-files>

# Complete merge
git commit -m "Merge: Resolved conflicts"
git push origin feature/task-name
```

### Accidentally Committed Sensitive Data

```bash
# Remove from history (use with caution!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/sensitive/file" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (notify team!)
git push origin --force --all

# Rotate compromised credentials immediately
```

### CI/CD Failing

```bash
# View CI/CD logs
# Fix issues locally
# Run tests locally
npm test

# Commit fix
git add .
git commit -m "[Fix] CI/CD failure - <description>"
git push origin feature/task-name
```

## Monitoring and Metrics

### Track Progress

```bash
# View commit statistics
git log --oneline | wc -l

# View commits by author
git shortlog -sn

# View commits by date
git log --since="2026-01-01" --oneline

# View file change statistics
git log --stat
```

### Code Review Metrics

- Average review time: < 24 hours
- Approval required: 1+ reviewers
- Changes requested: Address within 48 hours
- Merge to main: After all approvals

## Resources

### Git Documentation
- [Git Official Documentation](https://git-scm.com/doc)
- [Pro Git Book](https://git-scm.com/book/en/v2)
- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)

### GURU-Specific
- [tasks.md](.kiro/specs/guru-complete-system/tasks.md) - Implementation tasks
- [requirements.md](.kiro/specs/guru-complete-system/requirements.md) - Requirements
- [design.md](.kiro/specs/guru-complete-system/design.md) - Design document

---

**Remember**: Every commit is permanent. Every push is reviewed. Every merge is validated. Build with discipline. Ship with confidence.

**Last Updated**: January 15, 2026
**Maintained By**: GURU Development Team
