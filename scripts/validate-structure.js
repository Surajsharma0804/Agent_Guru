#!/usr/bin/env node

/**
 * GURU Production Structure Validator
 * 
 * Validates the complete system architecture and ensures all critical
 * components are properly structured for production deployment.
 * 
 * This validator enforces:
 * - Security boundary integrity
 * - Module dependency correctness
 * - Configuration completeness
 * - Platform abstraction layer consistency
 * - Test coverage requirements
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class ProductionStructureValidator {
    constructor() {
        this.errors = [];
        this.warnings = [];
        this.rootPath = process.cwd();
        this.requiredDirectories = [
            'desktop-agent/src/core',
            'desktop-agent/src/authority',
            'desktop-agent/src/biometric',
            'desktop-agent/src/language_model',
            'desktop-agent/src/platform_abstraction_layer',
            'desktop-agent/src/gui',
            'desktop-agent/src/memory',
            'desktop-agent/src/multilingual',
            'desktop-agent/src/intrusion',
            'desktop-agent/src/input',
            'desktop-agent/src/failure',
            'desktop-agent/tests/security',
            'desktop-agent/tests/properties',
            'shared/src/avatar',
            'shared/src/__tests__',
            'apps/android',
            'apps/ios',
            'apps/windows',
            'runtime/llm_adapter',
            'runtime/security',
            'docs'
        ];
        this.requiredFiles = [
            'desktop-agent/src/main_production.py',
            'desktop-agent/src/core/production_bootstrap.py',
            'desktop-agent/src/core/secure_execution_gateway.py',
            'desktop-agent/src/authority/authority_state_machine.py',
            'desktop-agent/src/biometric/biometric_authentication_providers.py',
            'desktop-agent/config/production.json',
            'shared/src/avatar/index.ts',
            'shared/src/avatar/implementations/IdentityManager.ts',
            'shared/src/avatar/implementations/UserControlManager.ts',
            'SECURITY_MODEL.md',
            'SYSTEM_MAP.md',
            'THREAD_MODEL.md'
        ];
    }

    async validate() {
        console.log('🔍 GURU Production Structure Validation');
        console.log('=====================================');
        
        this.validateDirectoryStructure();
        this.validateCriticalFiles();
        this.validateSecurityBoundaries();
        this.validatePlatformAbstraction();
        this.validateTestInfrastructure();
        this.validateDocumentation();
        this.validateDependencies();
        
        this.reportResults();
        
        if (this.errors.length > 0) {
            process.exit(1);
        }
    }

    validateDirectoryStructure() {
        console.log('\n📁 Validating Directory Structure...');
        
        for (const dir of this.requiredDirectories) {
            const fullPath = path.join(this.rootPath, dir);
            if (!fs.existsSync(fullPath)) {
                this.errors.push(`Missing critical directory: ${dir}`);
            } else {
                console.log(`  ✓ ${dir}`);
            }
        }
    }

    validateCriticalFiles() {
        console.log('\n📄 Validating Critical Files...');
        
        for (const file of this.requiredFiles) {
            const fullPath = path.join(this.rootPath, file);
            if (!fs.existsSync(fullPath)) {
                this.errors.push(`Missing critical file: ${file}`);
            } else {
                console.log(`  ✓ ${file}`);
            }
        }
    }

    validateSecurityBoundaries() {
        console.log('\n🔒 Validating Security Boundaries...');
        
        // Check authority state machine
        const authorityPath = path.join(this.rootPath, 'desktop-agent/src/authority/authority_state_machine.py');
        if (fs.existsSync(authorityPath)) {
            const content = fs.readFileSync(authorityPath, 'utf8');
            if (!content.includes('class AuthorityStateMachine')) {
                this.errors.push('Authority state machine class not found');
            } else {
                console.log('  ✓ Authority state machine structure');
            }
        }

        // Check biometric authentication
        const biometricPath = path.join(this.rootPath, 'desktop-agent/src/biometric/biometric_authentication_providers.py');
        if (fs.existsSync(biometricPath)) {
            const content = fs.readFileSync(biometricPath, 'utf8');
            if (!content.includes('class BiometricProvider')) {
                this.errors.push('Biometric authentication provider not found');
            } else {
                console.log('  ✓ Biometric authentication structure');
            }
        }

        // Check secure execution gateway
        const gatewayPath = path.join(this.rootPath, 'desktop-agent/src/core/secure_execution_gateway.py');
        if (fs.existsSync(gatewayPath)) {
            const content = fs.readFileSync(gatewayPath, 'utf8');
            if (!content.includes('SecureExecutionGateway')) {
                this.errors.push('Secure execution gateway not found');
            } else {
                console.log('  ✓ Secure execution gateway structure');
            }
        }
    }

    validatePlatformAbstraction() {
        console.log('\n🌐 Validating Platform Abstraction Layer...');
        
        const platforms = ['windows', 'macos', 'ios', 'android'];
        const palBase = path.join(this.rootPath, 'desktop-agent/src/platform_abstraction_layer/backends');
        
        for (const platform of platforms) {
            const platformPath = path.join(palBase, platform);
            if (!fs.existsSync(platformPath)) {
                this.errors.push(`Missing PAL backend for ${platform}`);
                continue;
            }

            const requiredModules = [
                'application_controller.py',
                'biometric_authenticator.py',
                'input_automation.py',
                'security_enforcer.py',
                'speech_input.py',
                'speech_output.py'
            ];

            for (const module of requiredModules) {
                const modulePath = path.join(platformPath, module);
                if (!fs.existsSync(modulePath)) {
                    this.errors.push(`Missing PAL module: ${platform}/${module}`);
                } else {
                    console.log(`  ✓ ${platform}/${module}`);
                }
            }
        }
    }

    validateTestInfrastructure() {
        console.log('\n🧪 Validating Test Infrastructure...');
        
        // Check property-based tests
        const propertyTestsPath = path.join(this.rootPath, 'shared/src/avatar/__tests__');
        if (fs.existsSync(propertyTestsPath)) {
            const files = fs.readdirSync(propertyTestsPath);
            const propertyTests = files.filter(f => f.includes('property.test.'));
            if (propertyTests.length === 0) {
                this.warnings.push('No property-based tests found in avatar system');
            } else {
                console.log(`  ✓ Found ${propertyTests.length} property-based test files`);
            }
        }

        // Check security tests
        const securityTestsPath = path.join(this.rootPath, 'desktop-agent/tests/security');
        if (fs.existsSync(securityTestsPath)) {
            const files = fs.readdirSync(securityTestsPath);
            if (files.length === 0) {
                this.errors.push('No security tests found');
            } else {
                console.log(`  ✓ Found ${files.length} security test files`);
            }
        }
    }

    validateDocumentation() {
        console.log('\n📚 Validating Documentation...');
        
        const criticalDocs = [
            'SECURITY_MODEL.md',
            'SYSTEM_MAP.md',
            'THREAD_MODEL.md',
            'GURU_PRODUCTION_ARCHITECTURE.md'
        ];

        for (const doc of criticalDocs) {
            const docPath = path.join(this.rootPath, doc);
            if (!fs.existsSync(docPath)) {
                this.errors.push(`Missing critical documentation: ${doc}`);
            } else {
                const content = fs.readFileSync(docPath, 'utf8');
                if (content.length < 1000) {
                    this.warnings.push(`Documentation ${doc} appears incomplete (< 1000 chars)`);
                } else {
                    console.log(`  ✓ ${doc}`);
                }
            }
        }
    }

    validateDependencies() {
        console.log('\n📦 Validating Dependencies...');
        
        // Check package.json files
        const packagePaths = [
            'package.json',
            'shared/package.json'
        ];

        for (const pkgPath of packagePaths) {
            const fullPath = path.join(this.rootPath, pkgPath);
            if (fs.existsSync(fullPath)) {
                try {
                    const pkg = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
                    if (!pkg.name || !pkg.version) {
                        this.errors.push(`Invalid package.json: ${pkgPath}`);
                    } else {
                        console.log(`  ✓ ${pkgPath} (${pkg.name}@${pkg.version})`);
                    }
                } catch (e) {
                    this.errors.push(`Malformed package.json: ${pkgPath}`);
                }
            }
        }

        // Check Python requirements
        const requirementsPath = path.join(this.rootPath, 'desktop-agent/requirements.txt');
        if (fs.existsSync(requirementsPath)) {
            const content = fs.readFileSync(requirementsPath, 'utf8');
            const lines = content.split('\n').filter(l => l.trim() && !l.startsWith('#'));
            if (lines.length === 0) {
                this.warnings.push('Empty Python requirements.txt');
            } else {
                console.log(`  ✓ Python requirements (${lines.length} packages)`);
            }
        }
    }

    reportResults() {
        console.log('\n📊 Validation Results');
        console.log('====================');
        
        if (this.errors.length === 0 && this.warnings.length === 0) {
            console.log('🎉 All validations passed! System structure is production-ready.');
            return;
        }

        if (this.errors.length > 0) {
            console.log('\n❌ ERRORS (must be fixed):');
            this.errors.forEach(error => console.log(`  • ${error}`));
        }

        if (this.warnings.length > 0) {
            console.log('\n⚠️  WARNINGS (should be addressed):');
            this.warnings.forEach(warning => console.log(`  • ${warning}`));
        }

        console.log(`\nSummary: ${this.errors.length} errors, ${this.warnings.length} warnings`);
    }
}

// Execute validation
const validator = new ProductionStructureValidator();
validator.validate().catch(error => {
    console.error('Validation failed:', error);
    process.exit(1);
});