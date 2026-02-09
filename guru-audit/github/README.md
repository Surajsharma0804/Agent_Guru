# GURU Production Audit System - GitHub Integration

Comprehensive GitHub integration with CI/CD automation, branch protection, status checks, and webhook handling.

## Overview

This module provides production-grade GitHub integration for the GURU Production Audit System, implementing:

- **GitHub API Integration**: Complete API client with retry logic, rate limiting, and error handling
- **CI/CD Pipeline Management**: Automated pipeline execution and result aggregation
- **Branch Protection Enforcement**: Zero-tolerance branch protection with required checks
- **Status Check Management**: Real-time status updates and failure notification
- **Webhook Handling**: Event processing with signature verification and routing

## Features

### GitHub API Integration

- Comprehensive GitHub API coverage
- Automatic retry with exponential backoff
- Rate limit handling and monitoring
- Authentication and signature verification
- Error handling with detailed diagnostics

### CI/CD Pipeline Management

- Automated workflow execution
- Real-time execution monitoring
- Result aggregation and reporting
- Quality metrics extraction
- Execution cancellation support

### Branch Protection Enforcement

- Audit system protection rules
- Required status checks enforcement
- Commit signature verification
- Merge prevention and control
- Protection rule validation

### Status Check Management

- Audit phase status tracking
- Real-time status updates
- Check run lifecycle management
- Result summary generation
- Failure notification

### Webhook Handling

- Signature verification
- Event routing and processing
- Duplicate event prevention
- Handler registration system
- Notification distribution

## Installation

```bash
npm install
```

## Usage

### GitHub API Integration

```typescript
import { GitHubApiIntegration } from './api_integration';

const apiClient = new GitHubApiIntegration({
  apiUrl: 'https://api.github.com',
  owner: 'your-org',
  repo: 'your-repo',
  token: 'your-token',
  timeout: 30000,
  maxRetries: 3,
  retryDelay: 1000,
});

// Get commit information
const commit = await apiClient.getCommit('sha');

// Create status check
await apiClient.createStatusCheck(
  'sha',
  'audit-system/phase-1',
  'success',
  'Phase 1 completed'
);
```

### CI/CD Pipeline Management

```typescript
import { CICDPipelineManager } from './cicd_pipeline_manager';

const pipelineManager = new CICDPipelineManager(apiClient);

// Execute audit phase pipeline
const result = await pipelineManager.executeAuditPhasePipeline(
  '1',
  'Full Inventory',
  'main'
);
```

### Branch Protection Enforcement

```typescript
import { BranchProtectionEnforcer } from './branch_protection_enforcer';

const enforcer = new BranchProtectionEnforcer(apiClient);

// Enforce audit system protection
await enforcer.enforceAuditSystemProtection('main');

// Check if merge is allowed
const { allowed, reasons } = await enforcer.checkMergeAllowed(123);
```

### Status Check Management

```typescript
import { StatusCheckManager } from './status_check_manager';

const statusManager = new StatusCheckManager(apiClient);

// Create audit phase check
const checkRun = await statusManager.createAuditPhaseCheck(
  '1',
  'Full Inventory',
  'sha'
);

// Update with result
await statusManager.updateCheckWithResult(checkRun.id, result);
```

### Webhook Handling

```typescript
import { WebhookHandler } from './webhook_handler';

const webhookHandler = new WebhookHandler({
  url: 'https://example.com/webhook',
  secret: 'your-secret',
  events: ['push', 'pull_request'],
  active: true,
});

// Register handler
webhookHandler.registerHandler('push', async (event) => {
  console.log('Push event received:', event);
});

// Process webhook
await webhookHandler.processWebhook(payload, signature, deliveryId);
```

## Testing

### Run Tests

```bash
npm test
```

### Run Property Tests

```bash
npm test -- property_tests.ts
```

### Run with Coverage

```bash
npm run test:coverage
```

## Performance Requirements

- GitHub API calls: ≤500ms per request
- CI/CD pipeline execution: ≤2 hours for complete audit cycle
- Branch protection enforcement: ≤10 seconds per check
- Status check updates: ≤5 seconds per update
- Webhook processing: ≤1 second per event

## Quality Standards

- Zero ESLint warnings
- 100% test coverage
- 10,000+ property test iterations
- Complete error handling
- Comprehensive documentation

## Architecture

The GitHub integration follows a modular architecture with clear separation of concerns:

```
github/
├── types.ts                          # Type definitions
├── api_integration.ts                # GitHub API client
├── cicd_pipeline_manager.ts          # Pipeline management
├── branch_protection_enforcer.ts     # Branch protection
├── status_check_manager.ts           # Status checks
├── webhook_handler.ts                # Webhook handling
├── property_tests.ts                 # Property-based tests
└── index.ts                          # Module exports
```

## Error Handling

All operations include comprehensive error handling with specific error types:

- `GitHubIntegrationError`: Base error class
- `RateLimitError`: Rate limit exceeded
- `AuthenticationError`: Authentication failed
- `ValidationError`: Validation failed

## Security

- Signature verification for all webhooks
- Secure token management
- Rate limiting protection
- Audit trail generation
- Zero-tolerance security policy

## License

PROPRIETARY - GURU Production Audit System

