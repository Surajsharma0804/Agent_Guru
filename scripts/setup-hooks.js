#!/usr/bin/env node

/**
 * GURU Personal Assistant - Git Hooks Setup
 * 
 * This script sets up security-focused git hooks to prevent
 * accidental commits of sensitive data.
 */

const fs = require('fs');
const path = require('path');

const PRE_COMMIT_HOOK = `#!/bin/sh
# GURU Personal Assistant - Pre-commit Security Hook

echo "🔍 Running GURU security pre-commit checks..."

# Check for forbidden files
echo "Checking for security-critical files..."
if git diff --cached --name-only | grep -E "\\.(key|pem|p12|pfx|crt|cer)$"; then
    echo "❌ ERROR: Attempting to commit cryptographic keys or certificates!"
    echo "These files should never be committed to version control."
    exit 1
fi

# Check for sensitive data patterns
echo "Scanning for sensitive data patterns..."
if git diff --cached | grep -E "(password|secret|key|token)\\s*=\\s*['\"][^'\"]+['\"]"; then
    echo "❌ ERROR: Potential sensitive data detected in commit!"
    echo "Please review and remove any hardcoded secrets."
    exit 1
fi

# Run structure validation
echo "Validating project structure..."
node scripts/validate-structure.js
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Project structure validation failed!"
    exit 1
fi

# Run permission validation
echo "Validating file permissions..."
node scripts/validate-permissions.js
if [ $? -ne 0 ]; then
    echo "❌ ERROR: File permission validation failed!"
    exit 1
fi

echo "✅ All pre-commit security checks passed!"
exit 0
`;

const PRE_PUSH_HOOK = `#!/bin/sh
# GURU Personal Assistant - Pre-push Security Hook

echo "🔍 Running GURU security pre-push checks..."

# Run security tests
echo "Running security test suite..."
npm run test:security
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Security tests failed!"
    exit 1
fi

# Run dependency security scan
echo "Scanning dependencies for vulnerabilities..."
npm audit --audit-level moderate
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Security vulnerabilities found in dependencies!"
    exit 1
fi

echo "✅ All pre-push security checks passed!"
exit 0
`;

class HookSetup {
  constructor() {
    this.rootPath = process.cwd();
    this.hooksPath = path.join(this.rootPath, '.git', 'hooks');
  }

  setup() {
    console.log('🔧 Setting up GURU security git hooks...\n');

    if (!fs.existsSync(path.join(this.rootPath, '.git'))) {
      console.log('⚠️  No .git directory found. Skipping git hooks setup.');
      console.log('   Run this script after initializing git repository.');
      return;
    }

    this.ensureHooksDirectory();
    this.installPreCommitHook();
    this.installPrePushHook();
    this.makeHooksExecutable();

    console.log('\n✅ Git hooks setup complete!');
    console.log('   Security checks will run automatically on commit and push.');
  }

  ensureHooksDirectory() {
    if (!fs.existsSync(this.hooksPath)) {
      fs.mkdirSync(this.hooksPath, { recursive: true });
      console.log('📁 Created .git/hooks directory');
    }
  }

  installPreCommitHook() {
    const hookPath = path.join(this.hooksPath, 'pre-commit');
    
    fs.writeFileSync(hookPath, PRE_COMMIT_HOOK);
    console.log('🔒 Installed pre-commit security hook');
  }

  installPrePushHook() {
    const hookPath = path.join(this.hooksPath, 'pre-push');
    
    fs.writeFileSync(hookPath, PRE_PUSH_HOOK);
    console.log('🔒 Installed pre-push security hook');
  }

  makeHooksExecutable() {
    try {
      const preCommitPath = path.join(this.hooksPath, 'pre-commit');
      const prePushPath = path.join(this.hooksPath, 'pre-push');
      
      fs.chmodSync(preCommitPath, '755');
      fs.chmodSync(prePushPath, '755');
      
      console.log('🔧 Made hooks executable');
    } catch (error) {
      console.log('⚠️  Could not set hook permissions:', error.message);
      console.log('   You may need to run: chmod +x .git/hooks/*');
    }
  }
}

// Run setup if called directly
if (require.main === module) {
  const setup = new HookSetup();
  setup.setup();
}

module.exports = HookSetup;