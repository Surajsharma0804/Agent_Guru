#!/usr/bin/env node

/**
 * GURU Production Permissions Validator
 * 
 * Validates that all system components have correct permissions
 * and security boundaries are properly enforced.
 */

const fs = require('fs');
const path = require('path');

class PermissionsValidator {
    constructor() {
        this.rootPath = process.cwd();
        this.errors = [];
        this.warnings = [];
    }

    async validate() {
        console.log('🔐 GURU Permissions Validation');
        console.log('==============================');
        
        this.validateFilePermissions();
        this.validateSecurityBoundaries();
        this.validateConfigurationSecurity();
        
        this.reportResults();
        
        if (this.errors.length > 0) {
            process.exit(1);
        }
    }

    validateFilePermissions() {
        console.log('\\n📁 Validating File Permissions...');
        
        const criticalFiles = [
            'desktop-agent/src/core/secure_execution_gateway.py',
            'desktop-agent/src/authority/authority_state_machine.py',
            'desktop-agent/src/biometric/biometric_authentication_providers.py'
        ];

        for (const file of criticalFiles) {
            const fullPath = path.join(this.rootPath, file);
            if (fs.existsSync(fullPath)) {
                const stats = fs.statSync(fullPath);
                const mode = stats.mode & parseInt('777', 8);
                
                if (mode & parseInt('002', 8)) {
                    this.errors.push(`Security file ${file} is world-writable`);
                } else {
                    console.log(`  ✓ ${file}`);
                }
            }
        }
    }

    validateSecurityBoundaries() {
        console.log('\\n🛡️  Validating Security Boundaries...');
        
        // Check for proper import restrictions
        const securityFiles = [
            'desktop-agent/src/authority/authority_state_machine.py',
            'desktop-agent/src/biometric/biometric_authentication_providers.py'
        ];

        for (const file of securityFiles) {
            const fullPath = path.join(this.rootPath, file);
            if (fs.existsSync(fullPath)) {
                const content = fs.readFileSync(fullPath, 'utf8');
                
                // Check for dangerous imports
                if (content.includes('import os') && !content.includes('# SECURITY: os import approved')) {
                    this.warnings.push(`Security file ${file} uses os module without approval comment`);
                }
                
                if (content.includes('subprocess') && !content.includes('# SECURITY: subprocess approved')) {
                    this.errors.push(`Security file ${file} uses subprocess without approval`);
                }
                
                console.log(`  ✓ ${file}`);
            }
        }
    }

    validateConfigurationSecurity() {
        console.log('\\n⚙️  Validating Configuration Security...');
        
        const configFiles = [
            'desktop-agent/config/production.json'
        ];

        for (const file of configFiles) {
            const fullPath = path.join(this.rootPath, file);
            if (fs.existsSync(fullPath)) {
                try {
                    const config = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
                    
                    // Check for hardcoded secrets
                    const configStr = JSON.stringify(config).toLowerCase();
                    const dangerousPatterns = ['password', 'secret', 'key', 'token'];
                    
                    for (const pattern of dangerousPatterns) {
                        if (configStr.includes(pattern) && !configStr.includes(`${pattern}_file`)) {
                            this.warnings.push(`Configuration ${file} may contain hardcoded ${pattern}`);
                        }
                    }
                    
                    console.log(`  ✓ ${file}`);
                } catch (e) {
                    this.errors.push(`Invalid JSON in configuration: ${file}`);
                }
            }
        }
    }

    reportResults() {
        console.log('\\n📊 Permissions Validation Results');
        console.log('=================================');
        
        if (this.errors.length === 0 && this.warnings.length === 0) {
            console.log('🎉 All permission validations passed!');
            return;
        }

        if (this.errors.length > 0) {
            console.log('\\n❌ ERRORS:');
            this.errors.forEach(error => console.log(`  • ${error}`));
        }

        if (this.warnings.length > 0) {
            console.log('\\n⚠️  WARNINGS:');
            this.warnings.forEach(warning => console.log(`  • ${warning}`));
        }
    }
}

const validator = new PermissionsValidator();
validator.validate().catch(error => {
    console.error('Permissions validation failed:', error);
    process.exit(1);
});