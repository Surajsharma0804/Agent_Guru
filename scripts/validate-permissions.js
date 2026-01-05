#!/usr/bin/env node

/**
 * GURU Personal Assistant - File Permissions Validation
 * 
 * This script validates file permissions to ensure security requirements
 * are met throughout the GURU project structure.
 */

const fs = require('fs');
const path = require('path');

// File permission requirements for different file types
const PERMISSION_REQUIREMENTS = {
  // Executable scripts
  scripts: {
    pattern: /\.(js|py|sh|bat)$/,
    directory: 'scripts',
    required: {
      owner: { read: true, write: true, execute: true },
      group: { read: true, write: false, execute: true },
      other: { read: true, write: false, execute: false }
    }
  },
  
  // Configuration files (should not be executable)
  config: {
    pattern: /\.(json|yaml|yml|toml|ini|conf)$/,
    directories: ['.', 'desktop-agent', 'phone-agent', 'shared', 'memory', 'skills', 'agents'],
    required: {
      owner: { read: true, write: true, execute: false },
      group: { read: true, write: false, execute: false },
      other: { read: true, write: false, execute: false }
    }
  },
  
  // Source code files
  source: {
    pattern: /\.(py|js|ts|kt|rs|c|cpp|h|hpp)$/,
    directories: ['desktop-agent', 'phone-agent', 'shared', 'memory', 'skills', 'agents'],
    required: {
      owner: { read: true, write: true, execute: false },
      group: { read: true, write: false, execute: false },
      other: { read: true, write: false, execute: false }
    }
  },
  
  // Documentation files
  docs: {
    pattern: /\.(md|txt|rst|adoc)$/,
    directories: ['.', 'docs'],
    required: {
      owner: { read: true, write: true, execute: false },
      group: { read: true, write: false, execute: false },
      other: { read: true, write: false, execute: false }
    }
  }
};

// Files that should never exist with certain permissions
const FORBIDDEN_PERMISSIONS = {
  // No files should be world-writable
  worldWritable: {
    check: (mode) => (mode & parseInt('002', 8)) !== 0,
    message: 'File is world-writable (security risk)'
  },
  
  // Executable files in non-script directories
  unexpectedExecutable: {
    check: (mode, filePath) => {
      const isExecutable = (mode & parseInt('111', 8)) !== 0;
      const isInScriptDir = filePath.includes('scripts/') || filePath.includes('infra/ci/');
      const isScript = /\.(js|py|sh|bat)$/.test(filePath);
      
      return isExecutable && !isInScriptDir && !isScript;
    },
    message: 'Unexpected executable file outside script directories'
  }
};

class PermissionValidator {
  constructor() {
    this.errors = [];
    this.warnings = [];
    this.rootPath = process.cwd();
  }

  /**
   * Validate file permissions across the project
   */
  validate() {
    console.log('🔐 Validating GURU file permissions...\n');
    
    this.validateDirectoryPermissions();
    this.validateFilePermissions();
    this.checkForbiddenPermissions();
    
    this.reportResults();
    
    return this.errors.length === 0;
  }

  /**
   * Validate directory permissions
   */
  validateDirectoryPermissions() {
    console.log('📁 Checking directory permissions...');
    
    const directories = [
      'desktop-agent',
      'phone-agent', 
      'shared',
      'memory',
      'skills',
      'agents',
      'infra/ci',
      'scripts'
    ];
    
    for (const dir of directories) {
      const dirPath = path.join(this.rootPath, dir);
      
      if (fs.existsSync(dirPath)) {
        try {
          const stats = fs.statSync(dirPath);
          const mode = stats.mode;
          
          // Directories should be readable and executable by owner and group
          const ownerPerms = (mode & parseInt('700', 8)) >> 6;
          const groupPerms = (mode & parseInt('070', 8)) >> 3;
          const otherPerms = mode & parseInt('007', 8);
          
          // Check owner permissions (should have read, write, execute)
          if ((ownerPerms & 7) !== 7) {
            this.errors.push(`Directory ${dir} missing owner permissions (need rwx)`);
          }
          
          // Check that directory is not world-writable
          if (otherPerms & 2) {
            this.errors.push(`Directory ${dir} is world-writable (security risk)`);
          }
          
          console.log(`  ✅ ${dir} directory permissions valid`);
        } catch (error) {
          this.warnings.push(`Could not check permissions for directory ${dir}: ${error.message}`);
        }
      }
    }
  }

  /**
   * Validate individual file permissions
   */
  validateFilePermissions() {
    console.log('\n📄 Checking file permissions...');
    
    for (const [category, config] of Object.entries(PERMISSION_REQUIREMENTS)) {
      const directories = Array.isArray(config.directories) ? config.directories : [config.directory];
      
      for (const dir of directories) {
        if (!dir) continue;
        
        const dirPath = path.join(this.rootPath, dir);
        
        if (fs.existsSync(dirPath)) {
          this.validateFilesInDirectory(dirPath, config, category);
        }
      }
    }
  }

  /**
   * Validate files in a specific directory
   */
  validateFilesInDirectory(dirPath, config, category) {
    try {
      const items = fs.readdirSync(dirPath);
      
      for (const item of items) {
        const itemPath = path.join(dirPath, item);
        const stats = fs.statSync(itemPath);
        
        if (stats.isFile() && config.pattern.test(item)) {
          this.validateFilePermission(itemPath, config.required, category);
        } else if (stats.isDirectory() && !item.startsWith('.') && 
                   !['node_modules', '__pycache__', 'build', 'dist', 'target'].includes(item)) {
          // Recursively check subdirectories
          this.validateFilesInDirectory(itemPath, config, category);
        }
      }
    } catch (error) {
      this.warnings.push(`Could not read directory ${dirPath}: ${error.message}`);
    }
  }

  /**
   * Validate permissions for a specific file
   */
  validateFilePermission(filePath, requiredPerms, category) {
    try {
      const stats = fs.statSync(filePath);
      const mode = stats.mode;
      const relativePath = path.relative(this.rootPath, filePath);
      
      // Extract permission bits
      const ownerPerms = (mode & parseInt('700', 8)) >> 6;
      const groupPerms = (mode & parseInt('070', 8)) >> 3;
      const otherPerms = mode & parseInt('007', 8);
      
      // Check owner permissions
      const ownerRead = (ownerPerms & 4) !== 0;
      const ownerWrite = (ownerPerms & 2) !== 0;
      const ownerExecute = (ownerPerms & 1) !== 0;
      
      if (requiredPerms.owner.read && !ownerRead) {
        this.errors.push(`${relativePath}: Owner missing read permission`);
      }
      if (requiredPerms.owner.write && !ownerWrite) {
        this.errors.push(`${relativePath}: Owner missing write permission`);
      }
      if (requiredPerms.owner.execute && !ownerExecute) {
        this.warnings.push(`${relativePath}: Owner missing execute permission (${category})`);
      }
      if (!requiredPerms.owner.execute && ownerExecute && category !== 'scripts') {
        this.warnings.push(`${relativePath}: Unexpected execute permission for ${category} file`);
      }
      
      // Check group permissions
      const groupRead = (groupPerms & 4) !== 0;
      const groupWrite = (groupPerms & 2) !== 0;
      const groupExecute = (groupPerms & 1) !== 0;
      
      if (requiredPerms.group.write && groupWrite) {
        this.warnings.push(`${relativePath}: Group has write permission (potential security risk)`);
      }
      
      // Check other permissions
      const otherWrite = (otherPerms & 2) !== 0;
      
      if (otherWrite) {
        this.errors.push(`${relativePath}: World-writable file (security risk)`);
      }
      
      console.log(`  ✅ ${relativePath} (${category})`);
      
    } catch (error) {
      this.warnings.push(`Could not check permissions for ${filePath}: ${error.message}`);
    }
  }

  /**
   * Check for forbidden permission patterns
   */
  checkForbiddenPermissions() {
    console.log('\n🚫 Checking for forbidden permission patterns...');
    
    this.scanForForbiddenPermissions(this.rootPath);
  }

  /**
   * Recursively scan for forbidden permissions
   */
  scanForForbiddenPermissions(dirPath, relativePath = '') {
    try {
      const items = fs.readdirSync(dirPath);
      
      for (const item of items) {
        const itemPath = path.join(dirPath, item);
        const relativeItemPath = path.join(relativePath, item);
        const stats = fs.statSync(itemPath);
        
        if (stats.isFile()) {
          const mode = stats.mode;
          
          // Check each forbidden permission pattern
          for (const [checkName, check] of Object.entries(FORBIDDEN_PERMISSIONS)) {
            if (check.check(mode, relativeItemPath)) {
              this.errors.push(`${relativeItemPath}: ${check.message}`);
            }
          }
        } else if (stats.isDirectory() && 
                   !item.startsWith('.') && 
                   !['node_modules', '__pycache__', 'build', 'dist', 'target'].includes(item)) {
          this.scanForForbiddenPermissions(itemPath, relativeItemPath);
        }
      }
    } catch (error) {
      // Directory might not be accessible
    }
  }

  /**
   * Report validation results
   */
  reportResults() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 PERMISSION VALIDATION RESULTS');
    console.log('='.repeat(60));
    
    if (this.errors.length === 0 && this.warnings.length === 0) {
      console.log('🎉 All permission validations passed! Security requirements met.');
      return;
    }
    
    if (this.errors.length > 0) {
      console.log('\n❌ PERMISSION ERRORS (must be fixed):');
      for (const error of this.errors) {
        console.log(`  • ${error}`);
      }
    }
    
    if (this.warnings.length > 0) {
      console.log('\n⚠️  PERMISSION WARNINGS (should be reviewed):');
      for (const warning of this.warnings) {
        console.log(`  • ${warning}`);
      }
    }
    
    console.log('\n' + '='.repeat(60));
    
    if (this.errors.length > 0) {
      console.log('❌ Permission validation failed. Fix errors before proceeding.');
      process.exit(1);
    } else {
      console.log('✅ Permission validation passed with warnings.');
    }
  }
}

// Run validation if called directly
if (require.main === module) {
  const validator = new PermissionValidator();
  validator.validate();
}

module.exports = PermissionValidator;