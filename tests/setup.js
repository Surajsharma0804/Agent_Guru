/**
 * GURU Personal Assistant - Test Setup
 * 
 * Global test configuration and security-focused test utilities
 */

// Extend Jest matchers for security testing
expect.extend({
  toBeSecureFile(received) {
    const fs = require('fs');
    const path = require('path');
    
    if (!fs.existsSync(received)) {
      return {
        message: () => `Expected file ${received} to exist`,
        pass: false
      };
    }
    
    const stats = fs.statSync(received);
    const mode = stats.mode;
    
    // Check if file is world-writable (security risk)
    const isWorldWritable = (mode & parseInt('002', 8)) !== 0;
    
    if (isWorldWritable) {
      return {
        message: () => `Expected file ${received} to not be world-writable`,
        pass: false
      };
    }
    
    return {
      message: () => `Expected file ${received} to be secure`,
      pass: true
    };
  },
  
  toContainSecurityPattern(received, pattern) {
    const contains = received.includes(pattern);
    
    return {
      message: () => contains 
        ? `Expected content to not contain security pattern "${pattern}"`
        : `Expected content to contain security pattern "${pattern}"`,
      pass: contains
    };
  },
  
  toHaveSecurePermissions(received) {
    const fs = require('fs');
    
    if (!fs.existsSync(received)) {
      return {
        message: () => `Expected path ${received} to exist`,
        pass: false
      };
    }
    
    try {
      const stats = fs.statSync(received);
      const mode = stats.mode;
      
      // Basic security check - not world-writable
      const isWorldWritable = (mode & parseInt('002', 8)) !== 0;
      
      return {
        message: () => isWorldWritable
          ? `Expected ${received} to have secure permissions (not world-writable)`
          : `Expected ${received} to have secure permissions`,
        pass: !isWorldWritable
      };
    } catch (error) {
      return {
        message: () => `Could not check permissions for ${received}: ${error.message}`,
        pass: false
      };
    }
  }
});

// Global test configuration
global.GURU_TEST_CONFIG = {
  // Security test settings
  security: {
    maxTestDuration: 30000,
    strictMode: true,
    validatePermissions: process.platform !== 'win32' // Skip on Windows
  },
  
  // File system test settings
  filesystem: {
    tempDir: require('os').tmpdir(),
    testDataDir: require('path').join(__dirname, 'data')
  },
  
  // Validation settings
  validation: {
    strictStructure: true,
    requireSecurityFiles: true,
    validateGitignore: true
  }
};

// Security-focused test utilities
global.SecurityTestUtils = {
  /**
   * Check if a file contains sensitive data patterns
   */
  containsSensitiveData(filePath) {
    const fs = require('fs');
    
    if (!fs.existsSync(filePath)) {
      return false;
    }
    
    const content = fs.readFileSync(filePath, 'utf8');
    const sensitivePatterns = [
      /password\s*=\s*['"][^'"]+['"]/i,
      /secret\s*=\s*['"][^'"]+['"]/i,
      /key\s*=\s*['"][^'"]+['"]/i,
      /token\s*=\s*['"][^'"]+['"]/i,
      /-----BEGIN [A-Z ]+-----/,
      /-----END [A-Z ]+-----/
    ];
    
    return sensitivePatterns.some(pattern => pattern.test(content));
  },
  
  /**
   * Validate that a directory structure meets security requirements
   */
  validateSecureStructure(basePath) {
    const fs = require('fs');
    const path = require('path');
    
    const requiredSecurityFiles = [
      '.gitignore',
      'SECURITY.md',
      'LICENSE'
    ];
    
    const results = {
      valid: true,
      errors: [],
      warnings: []
    };
    
    // Check required security files
    for (const file of requiredSecurityFiles) {
      const filePath = path.join(basePath, file);
      if (!fs.existsSync(filePath)) {
        results.valid = false;
        results.errors.push(`Missing required security file: ${file}`);
      }
    }
    
    // Check gitignore for security patterns
    const gitignorePath = path.join(basePath, '.gitignore');
    if (fs.existsSync(gitignorePath)) {
      const content = fs.readFileSync(gitignorePath, 'utf8');
      const requiredPatterns = ['*.key', '*.pem', 'audit_logs/', 'sensitive_data/'];
      
      for (const pattern of requiredPatterns) {
        if (!content.includes(pattern)) {
          results.warnings.push(`Gitignore missing security pattern: ${pattern}`);
        }
      }
    }
    
    return results;
  },
  
  /**
   * Generate test data that should be excluded by gitignore
   */
  generateTestSecurityFiles() {
    return [
      'test.key',
      'test.pem',
      'config.local.json',
      '.env.local',
      'credentials.txt',
      'audit_logs/test.log',
      'sensitive_data/test.dat'
    ];
  }
};

// Console override for test isolation
const originalConsole = global.console;
global.console = {
  ...originalConsole,
  log: process.env.NODE_ENV === 'test' ? () => {} : originalConsole.log,
  warn: originalConsole.warn,
  error: originalConsole.error
};

// Cleanup function for tests
global.afterEach(() => {
  // Reset any global state that might affect security tests
  delete process.env.TEST_SECURITY_OVERRIDE;
});

// Security test environment validation
beforeAll(() => {
  const requiredEnvVars = ['NODE_ENV'];
  const missingVars = requiredEnvVars.filter(varName => !process.env[varName]);
  
  if (missingVars.length > 0) {
    console.warn(`Warning: Missing environment variables: ${missingVars.join(', ')}`);
  }
  
  // Ensure we're in test mode
  if (process.env.NODE_ENV !== 'test') {
    process.env.NODE_ENV = 'test';
  }
});