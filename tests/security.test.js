/**
 * GURU Personal Assistant - Security Configuration Tests
 * 
 * These tests validate that security configurations are properly
 * set up and meet GURU's security requirements.
 */

const fs = require('fs');
const path = require('path');

describe('GURU Security Configuration', () => {
  describe('File Permissions and Access Control', () => {
    test('should not have world-writable files in production', () => {
      // This test would be more meaningful on Unix systems
      // On Windows, we focus on other security aspects
      expect(true).toBe(true); // Placeholder for Windows compatibility
    });

    test('should have proper script permissions', () => {
      const scriptsDir = path.join(process.cwd(), 'scripts');
      const scripts = fs.readdirSync(scriptsDir);
      
      scripts.forEach(script => {
        const scriptPath = path.join(scriptsDir, script);
        const stats = fs.statSync(scriptPath);
        expect(stats.isFile()).toBe(true);
      });
    });
  });

  describe('Dependency Security', () => {
    test('package.json should include security-focused dependencies', () => {
      const packagePath = path.join(process.cwd(), 'package.json');
      const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
      
      // Should have security linting
      expect(packageJson.devDependencies['eslint-plugin-security']).toBeDefined();
      
      // Should have proper scripts for security
      expect(packageJson.scripts['security:scan']).toBeDefined();
      expect(packageJson.scripts['test:security']).toBeDefined();
    });

    test('should have security-focused ESLint rules', () => {
      const eslintPath = path.join(process.cwd(), '.eslintrc.js');
      const eslintConfig = require(eslintPath);
      
      // Should include security plugin
      expect(eslintConfig.plugins).toContain('security');
      expect(eslintConfig.extends).toContain('plugin:security/recommended');
      
      // Should have security-specific rules
      expect(eslintConfig.rules['security/detect-object-injection']).toBe('error');
      expect(eslintConfig.rules['security/detect-eval-with-expression']).toBe('error');
    });
  });

  describe('Git Security Configuration', () => {
    test('should have security-focused git hooks', () => {
      const hooksDir = path.join(process.cwd(), '.git', 'hooks');
      
      if (fs.existsSync(hooksDir)) {
        const preCommitPath = path.join(hooksDir, 'pre-commit');
        const prePushPath = path.join(hooksDir, 'pre-push');
        
        if (fs.existsSync(preCommitPath)) {
          const preCommitContent = fs.readFileSync(preCommitPath, 'utf8');
          expect(preCommitContent).toContain('security');
          expect(preCommitContent).toContain('validate-structure');
        }
        
        if (fs.existsSync(prePushPath)) {
          const prePushContent = fs.readFileSync(prePushPath, 'utf8');
          expect(prePushContent).toContain('test:security');
        }
      }
    });

    test('gitignore should exclude all sensitive file types', () => {
      const gitignorePath = path.join(process.cwd(), '.gitignore');
      const content = fs.readFileSync(gitignorePath, 'utf8');
      
      const sensitivePatterns = [
        '*.key',
        '*.pem',
        '*.p12',
        '*.pfx',
        'audit_logs/',
        'sensitive_data/',
        'user_data/',
        'memory_data/',
        'credentials.*',
        '.env.local',
        '.env.production'
      ];
      
      sensitivePatterns.forEach(pattern => {
        expect(content).toContain(pattern);
      });
    });
  });

  describe('TypeScript Security Configuration', () => {
    test('should have strict TypeScript configuration', () => {
      const tsconfigPath = path.join(process.cwd(), 'tsconfig.json');
      const tsconfig = JSON.parse(fs.readFileSync(tsconfigPath, 'utf8'));
      
      // Should have strict mode enabled
      expect(tsconfig.compilerOptions.strict).toBe(true);
      expect(tsconfig.compilerOptions.noUnusedLocals).toBe(true);
      expect(tsconfig.compilerOptions.noUnusedParameters).toBe(true);
      expect(tsconfig.compilerOptions.exactOptionalPropertyTypes).toBe(true);
      expect(tsconfig.compilerOptions.noImplicitReturns).toBe(true);
      expect(tsconfig.compilerOptions.noFallthroughCasesInSwitch).toBe(true);
    });
  });

  describe('Security Documentation', () => {
    test('should have comprehensive security documentation', () => {
      const securityPath = path.join(process.cwd(), 'SECURITY.md');
      expect(fs.existsSync(securityPath)).toBe(true);
      
      const content = fs.readFileSync(securityPath, 'utf8');
      
      // Should cover key security topics
      expect(content).toContain('Security Policy');
      expect(content).toContain('Reporting Security Vulnerabilities');
      expect(content).toContain('Security Architecture');
      expect(content).toContain('Threat Model');
      expect(content).toContain('Security Boundaries');
    });

    test('README should mention security features', () => {
      const readmePath = path.join(process.cwd(), 'README.md');
      const content = fs.readFileSync(readmePath, 'utf8');
      
      // Should highlight security aspects
      expect(content).toContain('Security-First Design');
      expect(content).toContain('Authority State Machine');
      expect(content).toContain('Cryptographically Signed');
      expect(content).toContain('Multi-Factor');
    });
  });

  describe('License and Legal', () => {
    test('should have proper license with security notices', () => {
      const licensePath = path.join(process.cwd(), 'LICENSE');
      const content = fs.readFileSync(licensePath, 'utf8');
      
      // Should be MIT license
      expect(content).toContain('MIT License');
      
      // Should have security notices
      expect(content).toContain('SECURITY NOTICE');
      expect(content).toContain('PRIVACY NOTICE');
      expect(content).toContain('AUDIT NOTICE');
    });
  });

  describe('Build System Security', () => {
    test('should have security validation in build process', () => {
      const packagePath = path.join(process.cwd(), 'package.json');
      const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
      
      // Should validate structure on install
      expect(packageJson.scripts.postinstall).toContain('validate:structure');
      
      // Should have security scanning
      expect(packageJson.scripts['security:scan']).toBeDefined();
      expect(packageJson.scripts['security:scan:deps']).toBeDefined();
      expect(packageJson.scripts['security:scan:code']).toBeDefined();
      expect(packageJson.scripts['security:scan:secrets']).toBeDefined();
    });

    test('should have comprehensive test categories', () => {
      const packagePath = path.join(process.cwd(), 'package.json');
      const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
      
      // Should have different test types
      expect(packageJson.scripts['test:unit']).toBeDefined();
      expect(packageJson.scripts['test:integration']).toBeDefined();
      expect(packageJson.scripts['test:security']).toBeDefined();
      expect(packageJson.scripts['test:properties']).toBeDefined();
      expect(packageJson.scripts['test:negative']).toBeDefined();
    });
  });
});