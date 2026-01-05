#!/usr/bin/env node

/**
 * GURU Personal Assistant - Directory Structure Validation
 * 
 * This script validates that the monorepo structure meets security and
 * organizational requirements for the GURU project.
 */

const fs = require('fs');
const path = require('path');

// Required directory structure for GURU
const REQUIRED_STRUCTURE = {
  'desktop-agent': {
    type: 'directory',
    description: 'Windows Desktop Agent (FastAPI + Tauri)',
    required: true
  },
  'phone-agent': {
    type: 'directory', 
    description: 'Android Phone Agent (Kotlin + Compose)',
    required: true
  },
  'shared': {
    type: 'directory',
    description: 'Common utilities and protocols',
    required: true
  },
  'memory': {
    type: 'directory',
    description: 'MIRIX memory service implementation',
    required: true
  },
  'skills': {
    type: 'directory',
    description: 'Sandboxed skill system',
    required: true
  },
  'agents': {
    type: 'directory',
    description: 'LLM adapter and planning system',
    required: true
  },
  'infra/ci': {
    type: 'directory',
    description: 'CI/CD and deployment automation',
    required: true
  },
  'scripts': {
    type: 'directory',
    description: 'Build and validation scripts',
    required: true
  },
  '.gitignore': {
    type: 'file',
    description: 'Security-focused git exclusions',
    required: true
  },
  'LICENSE': {
    type: 'file',
    description: 'MIT License with security notices',
    required: true
  },
  'README.md': {
    type: 'file',
    description: 'Project documentation',
    required: true
  },
  'package.json': {
    type: 'file',
    description: 'Workspace management configuration',
    required: true
  }
};

// Security-critical files that should never exist
const FORBIDDEN_FILES = [
  '*.key',
  '*.pem',
  '*.p12',
  '*.pfx',
  'config.local.*',
  '.env.local',
  '.env.production',
  '.env.secrets',
  'credentials.*',
  'audit_logs/*',
  'sensitive_data/*',
  'user_data/*',
  'memory_data/*'
];

// Required security configurations
const SECURITY_REQUIREMENTS = {
  '.gitignore': {
    mustContain: [
      '# SECURITY-CRITICAL FILES',
      '*.key',
      '*.pem',
      'audit_logs/',
      'sensitive_data/',
      'user_data/'
    ]
  },
  'package.json': {
    mustContain: [
      '"test:security"',
      '"test:properties"',
      '"security:scan"',
      '"validate:permissions"'
    ]
  }
};

class StructureValidator {
  constructor() {
    this.errors = [];
    this.warnings = [];
    this.rootPath = process.cwd();
  }

  /**
   * Validate the complete directory structure
   */
  validate() {
    console.log('🔍 Validating GURU monorepo structure...\n');
    
    this.validateRequiredStructure();
    this.validateForbiddenFiles();
    this.validateSecurityConfigurations();
    this.validatePermissions();
    
    this.reportResults();
    
    return this.errors.length === 0;
  }

  /**
   * Check that all required directories and files exist
   */
  validateRequiredStructure() {
    console.log('📁 Checking required structure...');
    
    for (const [itemPath, config] of Object.entries(REQUIRED_STRUCTURE)) {
      const fullPath = path.join(this.rootPath, itemPath);
      
      if (!fs.existsSync(fullPath)) {
        if (config.required) {
          this.errors.push(`Missing required ${config.type}: ${itemPath}`);
        } else {
          this.warnings.push(`Missing optional ${config.type}: ${itemPath}`);
        }
        continue;
      }
      
      const stats = fs.statSync(fullPath);
      const actualType = stats.isDirectory() ? 'directory' : 'file';
      
      if (actualType !== config.type) {
        this.errors.push(
          `Incorrect type for ${itemPath}: expected ${config.type}, got ${actualType}`
        );
      } else {
        console.log(`  ✅ ${itemPath} (${config.description})`);
      }
    }
  }

  /**
   * Check that no security-critical files are present
   */
  validateForbiddenFiles() {
    console.log('\n🚫 Checking for forbidden security files...');
    
    const foundForbidden = [];
    
    // Simple check for common forbidden patterns
    const checkDirectory = (dirPath, relativePath = '') => {
      try {
        const items = fs.readdirSync(dirPath);
        
        for (const item of items) {
          const itemPath = path.join(dirPath, item);
          const relativeItemPath = path.join(relativePath, item);
          
          // Check against forbidden patterns
          for (const pattern of FORBIDDEN_FILES) {
            if (this.matchesPattern(item, pattern) || 
                this.matchesPattern(relativeItemPath, pattern)) {
              foundForbidden.push(relativeItemPath);
            }
          }
          
          // Recursively check subdirectories (but skip node_modules, .git, etc.)
          if (fs.statSync(itemPath).isDirectory() && 
              !['node_modules', '.git', '.pytest_cache', '__pycache__'].includes(item)) {
            checkDirectory(itemPath, relativeItemPath);
          }
        }
      } catch (error) {
        // Directory might not exist or be accessible
      }
    };
    
    checkDirectory(this.rootPath);
    
    if (foundForbidden.length > 0) {
      this.errors.push(`Found forbidden security files: ${foundForbidden.join(', ')}`);
    } else {
      console.log('  ✅ No forbidden security files found');
    }
  }

  /**
   * Validate security-critical configuration files
   */
  validateSecurityConfigurations() {
    console.log('\n🔒 Validating security configurations...');
    
    for (const [filePath, requirements] of Object.entries(SECURITY_REQUIREMENTS)) {
      const fullPath = path.join(this.rootPath, filePath);
      
      if (!fs.existsSync(fullPath)) {
        this.errors.push(`Missing security configuration file: ${filePath}`);
        continue;
      }
      
      try {
        const content = fs.readFileSync(fullPath, 'utf8');
        
        for (const requiredContent of requirements.mustContain) {
          if (!content.includes(requiredContent)) {
            this.errors.push(
              `${filePath} missing required security content: "${requiredContent}"`
            );
          }
        }
        
        console.log(`  ✅ ${filePath} security configuration valid`);
      } catch (error) {
        this.errors.push(`Failed to read security configuration ${filePath}: ${error.message}`);
      }
    }
  }

  /**
   * Validate file permissions for security
   */
  validatePermissions() {
    console.log('\n🔐 Validating file permissions...');
    
    const securityCriticalFiles = [
      'scripts/validate-structure.js',
      'scripts/validate-permissions.js'
    ];
    
    for (const filePath of securityCriticalFiles) {
      const fullPath = path.join(this.rootPath, filePath);
      
      if (fs.existsSync(fullPath)) {
        try {
          const stats = fs.statSync(fullPath);
          const mode = stats.mode;
          
          // Check if file is executable (for scripts)
          if (filePath.endsWith('.js') && !(mode & parseInt('100', 8))) {
            this.warnings.push(`Script ${filePath} is not executable`);
          }
          
          console.log(`  ✅ ${filePath} permissions valid`);
        } catch (error) {
          this.warnings.push(`Could not check permissions for ${filePath}: ${error.message}`);
        }
      }
    }
  }

  /**
   * Simple pattern matching for forbidden files
   */
  matchesPattern(filename, pattern) {
    // Convert glob-like pattern to regex
    const regexPattern = pattern
      .replace(/\./g, '\\.')
      .replace(/\*/g, '.*')
      .replace(/\?/g, '.');
    
    const regex = new RegExp(`^${regexPattern}$`);
    return regex.test(filename);
  }

  /**
   * Report validation results
   */
  reportResults() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 VALIDATION RESULTS');
    console.log('='.repeat(60));
    
    if (this.errors.length === 0 && this.warnings.length === 0) {
      console.log('🎉 All validations passed! Structure is secure and complete.');
      return;
    }
    
    if (this.errors.length > 0) {
      console.log('\n❌ ERRORS (must be fixed):');
      for (const error of this.errors) {
        console.log(`  • ${error}`);
      }
    }
    
    if (this.warnings.length > 0) {
      console.log('\n⚠️  WARNINGS (should be addressed):');
      for (const warning of this.warnings) {
        console.log(`  • ${warning}`);
      }
    }
    
    console.log('\n' + '='.repeat(60));
    
    if (this.errors.length > 0) {
      console.log('❌ Validation failed. Please fix errors before proceeding.');
      process.exit(1);
    } else {
      console.log('✅ Validation passed with warnings. Review warnings when possible.');
    }
  }
}

// Run validation if called directly
if (require.main === module) {
  const validator = new StructureValidator();
  validator.validate();
}

module.exports = StructureValidator;