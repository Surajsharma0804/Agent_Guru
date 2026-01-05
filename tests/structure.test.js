/**
 * GURU Personal Assistant - Structure Validation Tests
 * 
 * These tests validate that the monorepo structure meets all
 * security and organizational requirements.
 */

const fs = require('fs');
const path = require('path');
const StructureValidator = require('../scripts/validate-structure');

describe('GURU Monorepo Structure', () => {
  let validator;
  
  beforeEach(() => {
    validator = new StructureValidator();
  });

  describe('Required Directories', () => {
    const requiredDirs = [
      'desktop-agent',
      'phone-agent',
      'shared',
      'memory',
      'skills',
      'agents',
      'infra/ci',
      'scripts'
    ];

    test.each(requiredDirs)('should have %s directory', (dir) => {
      const dirPath = path.join(process.cwd(), dir);
      expect(fs.existsSync(dirPath)).toBe(true);
      expect(fs.statSync(dirPath).isDirectory()).toBe(true);
    });
  });

  describe('Required Files', () => {
    const requiredFiles = [
      '.gitignore',
      'LICENSE',
      'README.md',
      'package.json',
      'tsconfig.json',
      'SECURITY.md'
    ];

    test.each(requiredFiles)('should have %s file', (file) => {
      const filePath = path.join(process.cwd(), file);
      expect(fs.existsSync(filePath)).toBe(true);
      expect(fs.statSync(filePath).isFile()).toBe(true);
    });
  });

  describe('Security Configuration', () => {
    test('gitignore should contain security exclusions', () => {
      const gitignorePath = path.join(process.cwd(), '.gitignore');
      const content = fs.readFileSync(gitignorePath, 'utf8');
      
      const requiredPatterns = [
        '*.key',
        '*.pem',
        'audit_logs/',
        'sensitive_data/',
        'user_data/'
      ];
      
      requiredPatterns.forEach(pattern => {
        expect(content).toContain(pattern);
      });
    });

    test('package.json should contain security scripts', () => {
      const packagePath = path.join(process.cwd(), 'package.json');
      const content = fs.readFileSync(packagePath, 'utf8');
      
      const requiredScripts = [
        'test:security',
        'test:properties',
        'security:scan',
        'validate:permissions'
      ];
      
      requiredScripts.forEach(script => {
        expect(content).toContain(`"${script}"`);
      });
    });
  });

  describe('Forbidden Files', () => {
    test('should not contain cryptographic keys', () => {
      const forbiddenPatterns = [
        '*.key',
        '*.pem',
        '*.p12',
        '*.pfx'
      ];
      
      // This is a simplified check - in practice, we'd scan the entire tree
      const rootFiles = fs.readdirSync(process.cwd());
      
      forbiddenPatterns.forEach(pattern => {
        const regex = new RegExp(pattern.replace('*', '.*'));
        const matches = rootFiles.filter(file => regex.test(file));
        expect(matches).toHaveLength(0);
      });
    });
  });

  describe('Workspace Configuration', () => {
    test('package.json should define workspaces', () => {
      const packagePath = path.join(process.cwd(), 'package.json');
      const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
      
      expect(packageJson.workspaces).toBeDefined();
      expect(Array.isArray(packageJson.workspaces)).toBe(true);
      expect(packageJson.workspaces).toContain('desktop-agent');
      expect(packageJson.workspaces).toContain('phone-agent');
      expect(packageJson.workspaces).toContain('shared');
    });

    test('tsconfig.json should define path mappings', () => {
      const tsconfigPath = path.join(process.cwd(), 'tsconfig.json');
      const tsconfig = JSON.parse(fs.readFileSync(tsconfigPath, 'utf8'));
      
      expect(tsconfig.compilerOptions.paths).toBeDefined();
      expect(tsconfig.compilerOptions.paths['@guru/shared/*']).toBeDefined();
      expect(tsconfig.compilerOptions.paths['@guru/desktop-agent/*']).toBeDefined();
    });
  });

  describe('Build System Integration', () => {
    test('should have validation scripts', () => {
      const scriptsDir = path.join(process.cwd(), 'scripts');
      const scripts = fs.readdirSync(scriptsDir);
      
      expect(scripts).toContain('validate-structure.js');
      expect(scripts).toContain('validate-permissions.js');
      expect(scripts).toContain('setup-hooks.js');
    });

    test('validation scripts should be functional', () => {
      // Test that the validator can be instantiated and run
      expect(() => {
        const result = validator.validate();
        // Should return boolean
        expect(typeof result).toBe('boolean');
      }).not.toThrow();
    });
  });

  describe('Security Defaults', () => {
    test('should have secure ESLint configuration', () => {
      const eslintPath = path.join(process.cwd(), '.eslintrc.js');
      expect(fs.existsSync(eslintPath)).toBe(true);
      
      const eslintConfig = require(eslintPath);
      expect(eslintConfig.plugins).toContain('security');
      expect(eslintConfig.extends).toContain('plugin:security/recommended');
    });

    test('should have comprehensive gitignore', () => {
      const gitignorePath = path.join(process.cwd(), '.gitignore');
      const content = fs.readFileSync(gitignorePath, 'utf8');
      
      // Should have security section
      expect(content).toContain('SECURITY-CRITICAL FILES');
      
      // Should exclude common sensitive patterns
      expect(content).toContain('*.key');
      expect(content).toContain('*.pem');
      expect(content).toContain('audit_logs/');
      expect(content).toContain('sensitive_data/');
    });
  });
});