/**
 * Jest test setup for avatar system
 */

// Extend Jest matchers for better assertions
expect.extend({
  toBeWithinRange(received: number, floor: number, ceiling: number) {
    const pass = received >= floor && received <= ceiling;
    if (pass) {
      return {
        message: () =>
          `expected ${received} not to be within range ${floor} - ${ceiling}`,
        pass: true,
      };
    } else {
      return {
        message: () =>
          `expected ${received} to be within range ${floor} - ${ceiling}`,
        pass: false,
      };
    }
  },
  
  toBeValidAvatarApiResponse(received: any) {
    const hasRequiredFields = 
      typeof received === 'object' &&
      received !== null &&
      typeof received.success === 'boolean' &&
      typeof received.executionTime === 'number' &&
      typeof received.timestamp === 'number';
    
    if (hasRequiredFields) {
      return {
        message: () => `expected ${JSON.stringify(received)} not to be a valid AvatarApiResponse`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${JSON.stringify(received)} to be a valid AvatarApiResponse with success, executionTime, and timestamp fields`,
        pass: false,
      };
    }
  }
});

// Global test configuration
global.console = {
  ...console,
  // Suppress console.log in tests unless explicitly needed
  log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: console.warn,
  error: console.error,
};

// Mock performance.now for consistent timing in tests
Object.defineProperty(global, 'performance', {
  writable: true,
  value: {
    now: jest.fn(() => Date.now()),
  },
});

// Set up default test timeouts for different test types
const DEFAULT_TIMEOUT = 5000;

beforeEach(() => {
  // Reset timeout to default
  jest.setTimeout(DEFAULT_TIMEOUT);
  
  // Detect property-based tests and increase timeout
  const testName = expect.getState().currentTestName || '';
  if (testName.includes('Property') || testName.includes('property')) {
    jest.setTimeout(30000); // 30 seconds for property tests
  }
});

// Clean up after each test
afterEach(() => {
  jest.clearAllMocks();
  jest.clearAllTimers();
});