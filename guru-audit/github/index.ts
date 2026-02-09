/**
 * GURU Production Audit System - GitHub Integration
 *
 * Comprehensive GitHub integration with CI/CD automation, branch protection,
 * status checks, and webhook handling.
 *
 * MAXIMUM ENGINEERING MANDATE:
 * - Production-grade GitHub integration with zero compromises
 * - Complete automation with comprehensive error handling
 * - Full lifecycle management for all GitHub operations
 * - 20+ year maintenance lifecycle design
 */

// Export types
export * from './types';

// Export API integration
export { GitHubApiIntegration } from './api_integration';

// Export CI/CD pipeline manager
export { CICDPipelineManager } from './cicd_pipeline_manager';

// Export branch protection enforcer
export { BranchProtectionEnforcer } from './branch_protection_enforcer';

// Export status check manager
export { StatusCheckManager } from './status_check_manager';

// Export webhook handler
export { WebhookHandler } from './webhook_handler';
export type { WebhookEventHandler } from './webhook_handler';

