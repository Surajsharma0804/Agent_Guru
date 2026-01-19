#!/usr/bin/env node

/**
 * GURU Production Git Hooks Setup
 * 
 * Establishes comprehensive git hooks for production-grade development:
 * - Pre-commit: Security scanning, linting, type checking
 * - Pre-push: Full test suite, security validation
 * - Post-merge: Dependency updates, structure validation
 * - Commit-msg: Conventional commit format enforcement
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class ProductionHooksSetup {
    constructor() {
        this.rootPath = process.cwd();
        this.hooksPath = path.join(this.rootPath, '.git/hooks');
        this.scriptsPath = path.join(this.rootPath, 'scripts');
    }

    async setup() {
        console.log('🔧 Setting up GURU Production Git Hooks');
        console.log('=======================================');
        
        this.ensureHooksDirectory();
        this.setupPreCommitHook();
        this.setupPrePushHook();
        this.setupPostMergeHook();
        this.setupCommitMsgHook();
        this.setupHuskyIntegration();
        
        console.log('\n✅ Git hooks setup complete!');
        console.log('All commits will now be validated for production standards.');
    }

    ensureHooksDirectory() {
        if (!fs.existsSync(this.hooksPath)) {
            console.log('⚠️  Git hooks directory not found. Initializing git repository...');
            try {
                execSync('git init', { cwd: this.rootPath });
                console.log('✓ Git repository initialized');
            } catch (error) {
                console.log('ℹ️  Git hooks will be set up when repository is initialized');
                return;
            }
        }
    }

    setupPreCommitHook() {
        const hookContent = `#!/bin/sh
# GURU Production Pre-Commit Hook
# Ensures all commits meet production standards

set -e

echo "🔍 GURU Pre-Commit Validation"
echo "============================="

# 1. Security Scanning
echo "\\n🔒 Running security scans..."
npm run security:scan:secrets || {
    echo "❌ Security scan failed - commit blocked"
    exit 1
}

# 2. Linting and Formatting
echo "\\n🧹 Running linters..."
npm run lint || {
    echo "❌ Linting failed - commit blocked"
    echo "Run 'npm run format' to fix formatting issues"
    exit 1
}

# 3. Type Checking
echo "\\n🔍 Type checking..."
cd shared && npm run build || {
    echo "❌ TypeScript compilation failed - commit blocked"
    exit 1
}

# 4. Unit Tests (fast subset)
echo "\\n🧪 Running unit tests..."
npm run test:unit || {
    echo "❌ Unit tests failed - commit blocked"
    exit 1
}

# 5. Authority System Validation
echo "\\n🛡️  Validating authority system..."
cd desktop-agent && python -m pytest tests/security/test_authority.py -v || {
    echo "❌ Authority system validation failed - commit blocked"
    exit 1
}

echo "\\n✅ Pre-commit validation passed!"
`;

        this.writeHook('pre-commit', hookContent);
    }

    setupPrePushHook() {
        const hookContent = `#!/bin/sh
# GURU Production Pre-Push Hook
# Comprehensive validation before pushing to remote

set -e

echo "🚀 GURU Pre-Push Validation"
echo "=========================="

# 1. Full Test Suite
echo "\\n🧪 Running full test suite..."
npm run test || {
    echo "❌ Test suite failed - push blocked"
    exit 1
}

# 2. Security Validation
echo "\\n🔒 Running security validation..."
npm run validate:security || {
    echo "❌ Security validation failed - push blocked"
    exit 1
}

# 3. Property-Based Tests
echo "\\n🔬 Running property-based tests..."
npm run test:properties || {
    echo "❌ Property-based tests failed - push blocked"
    exit 1
}

# 4. Integration Tests
echo "\\n🔗 Running integration tests..."
npm run test:integration || {
    echo "❌ Integration tests failed - push blocked"
    exit 1
}

# 5. Production Build Verification
echo "\\n🏗️  Verifying production build..."
npm run build || {
    echo "❌ Production build failed - push blocked"
    exit 1
}

echo "\\n✅ Pre-push validation passed!"
echo "🎉 Ready for production deployment!"
`;

        this.writeHook('pre-push', hookContent);
    }

    setupPostMergeHook() {
        const hookContent = `#!/bin/sh
# GURU Production Post-Merge Hook
# Maintains system integrity after merges

set -e

echo "🔄 GURU Post-Merge Maintenance"
echo "============================="

# 1. Dependency Updates
echo "\\n📦 Checking dependencies..."
npm install || {
    echo "⚠️  Dependency installation failed"
}

# 2. Structure Validation
echo "\\n📁 Validating structure..."
npm run validate:structure || {
    echo "⚠️  Structure validation failed - manual review required"
}

# 3. Rebuild Shared Components
echo "\\n🔧 Rebuilding shared components..."
npm run build:shared || {
    echo "⚠️  Shared component build failed"
}

echo "\\n✅ Post-merge maintenance complete!"
`;

        this.writeHook('post-merge', hookContent);
    }

    setupCommitMsgHook() {
        const hookContent = `#!/bin/sh
# GURU Production Commit Message Hook
# Enforces conventional commit format

commit_regex='^(feat|fix|docs|style|refactor|test|chore|security|perf|build|ci|revert)(\\(.+\\))?: .{1,50}'

if ! grep -qE "$commit_regex" "$1"; then
    echo "❌ Invalid commit message format!"
    echo ""
    echo "GURU requires conventional commit format:"
    echo "  type(scope): description"
    echo ""
    echo "Types: feat, fix, docs, style, refactor, test, chore, security, perf, build, ci, revert"
    echo ""
    echo "Examples:"
    echo "  feat(auth): add biometric authentication"
    echo "  fix(security): resolve authority state race condition"
    echo "  docs(api): update security model documentation"
    echo ""
    exit 1
fi

# Check for security-related commits
if grep -qE "(security|auth|crypto|biometric|authority)" "$1"; then
    echo "🔒 Security-related commit detected"
    echo "Ensure security review is completed before merging"
fi
`;

        this.writeHook('commit-msg', hookContent);
    }

    setupHuskyIntegration() {
        console.log('\\n🐕 Setting up Husky integration...');
        
        try {
            // Install husky if not already installed
            execSync('npm list husky', { cwd: this.rootPath, stdio: 'ignore' });
            console.log('✓ Husky already installed');
        } catch (error) {
            console.log('Installing Husky...');
            execSync('npm install --save-dev husky', { cwd: this.rootPath });
        }

        // Initialize husky
        try {
            execSync('npx husky install', { cwd: this.rootPath });
            console.log('✓ Husky initialized');
        } catch (error) {
            console.log('ℹ️  Husky initialization skipped (may already be configured)');
        }
    }

    writeHook(hookName, content) {
        const hookPath = path.join(this.hooksPath, hookName);
        
        try {
            fs.writeFileSync(hookPath, content, { mode: 0o755 });
            console.log(`✓ ${hookName} hook installed`);
        } catch (error) {
            console.log(`ℹ️  ${hookName} hook will be installed when git repository is available`);
        }
    }
}

// Execute setup
const setup = new ProductionHooksSetup();
setup.setup().catch(error => {
    console.error('Hook setup failed:', error);
    process.exit(1);
});