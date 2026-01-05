module.exports = {
  // Test environment
  testEnvironment: 'node',
  
  // Test file patterns
  testMatch: [
    '**/tests/**/*.test.js',
    '**/tests/**/*.spec.js',
    '**/__tests__/**/*.js'
  ],
  
  // Coverage configuration
  collectCoverage: true,
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  
  // Coverage thresholds for security-critical code
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  
  // Files to collect coverage from
  collectCoverageFrom: [
    'scripts/**/*.js',
    'shared/src/**/*.js',
    'shared/src/**/*.ts',
    '!**/node_modules/**',
    '!**/coverage/**',
    '!**/dist/**',
    '!**/build/**'
  ],
  
  // Setup files
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
  
  // Module name mapping for monorepo
  moduleNameMapper: {
    '^@guru/shared/(.*)$': '<rootDir>/shared/src/$1',
    '^@guru/desktop-agent/(.*)$': '<rootDir>/desktop-agent/src/$1',
    '^@guru/memory/(.*)$': '<rootDir>/memory/src/$1',
    '^@guru/skills/(.*)$': '<rootDir>/skills/src/$1',
    '^@guru/agents/(.*)$': '<rootDir>/agents/src/$1'
  },
  
  // Transform configuration
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
    '^.+\\.jsx?$': 'babel-jest'
  },
  
  // File extensions to consider
  moduleFileExtensions: ['js', 'jsx', 'ts', 'tsx', 'json', 'node'],
  
  // Test timeout (important for security tests that may take longer)
  testTimeout: 30000,
  
  // Verbose output for security validation
  verbose: true,
  
  // Clear mocks between tests for security isolation
  clearMocks: true,
  restoreMocks: true,
  
  // Global test configuration
  globals: {
    'ts-jest': {
      useESM: true
    }
  },
  
  // Test result processor for security reporting
  testResultsProcessor: '<rootDir>/tests/security-results-processor.js'
};