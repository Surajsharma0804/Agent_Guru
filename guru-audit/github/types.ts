/**
 * GitHub Integration Types
 *
 * Comprehensive type definitions for GitHub API integration, CI/CD pipeline management,
 * branch protection, status checks, and webhook handling.
 *
 * MAXIMUM ENGINEERING MANDATE:
 * - Production-grade type safety with complete API coverage
 * - Zero tolerance for type errors or unsafe operations
 * - Comprehensive error handling and validation
 * - 20+ year maintenance lifecycle design
 */

/**
 * GitHub API configuration
 */
export interface GitHubConfig {
  /** GitHub API base URL */
  apiUrl: string;
  /** Repository owner */
  owner: string;
  /** Repository name */
  repo: string;
  /** Authentication token */
  token: string;
  /** API timeout in milliseconds */
  timeout: number;
  /** Maximum retry attempts */
  maxRetries: number;
  /** Retry delay in milliseconds */
  retryDelay: number;
}

/**
 * GitHub API response wrapper
 */
export interface GitHubApiResponse<T> {
  /** Response data */
  data: T;
  /** HTTP status code */
  status: number;
  /** Response headers */
  headers: Record<string, string>;
  /** Rate limit information */
  rateLimit: RateLimitInfo;
}

/**
 * Rate limit information
 */
export interface RateLimitInfo {
  /** Remaining requests */
  remaining: number;
  /** Rate limit reset timestamp */
  reset: number;
  /** Total rate limit */
  limit: number;
}

/**
 * Commit information
 */
export interface CommitInfo {
  /** Commit SHA */
  sha: string;
  /** Commit message */
  message: string;
  /** Author information */
  author: AuthorInfo;
  /** Committer information */
  committer: AuthorInfo;
  /** Commit timestamp */
  timestamp: Date;
  /** Parent commit SHAs */
  parents: string[];
  /** Commit signature verification */
  verification: SignatureVerification;
}

/**
 * Author/Committer information
 */
export interface AuthorInfo {
  /** Name */
  name: string;
  /** Email */
  email: string;
  /** Username */
  username?: string;
}

/**
 * Signature verification
 */
export interface SignatureVerification {
  /** Verification status */
  verified: boolean;
  /** Verification reason */
  reason: string;
  /** Signature */
  signature: string | null;
  /** Payload */
  payload: string | null;
}

/**
 * Pull request information
 */
export interface PullRequestInfo {
  /** PR number */
  number: number;
  /** PR title */
  title: string;
  /** PR description */
  body: string;
  /** PR state */
  state: 'open' | 'closed' | 'merged';
  /** Head branch */
  head: BranchInfo;
  /** Base branch */
  base: BranchInfo;
  /** PR author */
  author: AuthorInfo;
  /** Created timestamp */
  createdAt: Date;
  /** Updated timestamp */
  updatedAt: Date;
  /** Merged timestamp */
  mergedAt: Date | null;
  /** Mergeable state */
  mergeable: boolean | null;
  /** Mergeable state status */
  mergeableState: string;
}

/**
 * Branch information
 */
export interface BranchInfo {
  /** Branch name */
  ref: string;
  /** Branch SHA */
  sha: string;
  /** Repository information */
  repo: RepositoryInfo;
}

/**
 * Repository information
 */
export interface RepositoryInfo {
  /** Repository ID */
  id: number;
  /** Repository name */
  name: string;
  /** Repository full name */
  fullName: string;
  /** Repository owner */
  owner: AuthorInfo;
  /** Repository URL */
  url: string;
}

/**
 * Status check information
 */
export interface StatusCheckInfo {
  /** Status check context */
  context: string;
  /** Status check state */
  state: 'pending' | 'success' | 'failure' | 'error';
  /** Status check description */
  description: string;
  /** Target URL */
  targetUrl: string | null;
  /** Created timestamp */
  createdAt: Date;
  /** Updated timestamp */
  updatedAt: Date;
}

/**
 * Check run information
 */
export interface CheckRunInfo {
  /** Check run ID */
  id: number;
  /** Check run name */
  name: string;
  /** Check run status */
  status: 'queued' | 'in_progress' | 'completed';
  /** Check run conclusion */
  conclusion: 'success' | 'failure' | 'neutral' | 'cancelled' | 'skipped' | 'timed_out' | 'action_required' | null;
  /** Started timestamp */
  startedAt: Date | null;
  /** Completed timestamp */
  completedAt: Date | null;
  /** Output */
  output: CheckRunOutput;
  /** Details URL */
  detailsUrl: string | null;
}

/**
 * Check run output
 */
export interface CheckRunOutput {
  /** Output title */
  title: string;
  /** Output summary */
  summary: string;
  /** Output text */
  text: string;
  /** Annotations */
  annotations: CheckRunAnnotation[];
}

/**
 * Check run annotation
 */
export interface CheckRunAnnotation {
  /** File path */
  path: string;
  /** Start line */
  startLine: number;
  /** End line */
  endLine: number;
  /** Annotation level */
  level: 'notice' | 'warning' | 'failure';
  /** Annotation message */
  message: string;
  /** Title */
  title: string | null;
  /** Raw details */
  rawDetails: string | null;
}

/**
 * Branch protection rules
 */
export interface BranchProtectionRules {
  /** Require pull request reviews */
  requiredPullRequestReviews: RequiredPullRequestReviews | null;
  /** Required status checks */
  requiredStatusChecks: RequiredStatusChecks | null;
  /** Enforce admins */
  enforceAdmins: boolean;
  /** Require linear history */
  requireLinearHistory: boolean;
  /** Allow force pushes */
  allowForcePushes: boolean;
  /** Allow deletions */
  allowDeletions: boolean;
  /** Required signatures */
  requiredSignatures: boolean;
}

/**
 * Required pull request reviews
 */
export interface RequiredPullRequestReviews {
  /** Dismiss stale reviews */
  dismissStaleReviews: boolean;
  /** Require code owner reviews */
  requireCodeOwnerReviews: boolean;
  /** Required approving review count */
  requiredApprovingReviewCount: number;
}

/**
 * Required status checks
 */
export interface RequiredStatusChecks {
  /** Strict mode */
  strict: boolean;
  /** Required contexts */
  contexts: string[];
}

/**
 * Webhook event
 */
export interface WebhookEvent {
  /** Event type */
  event: string;
  /** Event action */
  action: string;
  /** Event payload */
  payload: Record<string, unknown>;
  /** Delivery ID */
  deliveryId: string;
  /** Signature */
  signature: string;
  /** Timestamp */
  timestamp: Date;
}

/**
 * Webhook configuration
 */
export interface WebhookConfig {
  /** Webhook URL */
  url: string;
  /** Webhook secret */
  secret: string;
  /** Events to subscribe to */
  events: string[];
  /** Active status */
  active: boolean;
}

/**
 * CI/CD pipeline configuration
 */
export interface CICDPipelineConfig {
  /** Pipeline name */
  name: string;
  /** Workflow file path */
  workflowPath: string;
  /** Trigger events */
  triggers: PipelineTrigger[];
  /** Pipeline jobs */
  jobs: PipelineJob[];
  /** Environment variables */
  env: Record<string, string>;
  /** Timeout in minutes */
  timeout: number;
}

/**
 * Pipeline trigger
 */
export interface PipelineTrigger {
  /** Trigger type */
  type: 'push' | 'pull_request' | 'schedule' | 'workflow_dispatch';
  /** Trigger configuration */
  config: Record<string, unknown>;
}

/**
 * Pipeline job
 */
export interface PipelineJob {
  /** Job ID */
  id: string;
  /** Job name */
  name: string;
  /** Job steps */
  steps: PipelineStep[];
  /** Job dependencies */
  needs: string[];
  /** Runs on */
  runsOn: string;
  /** Job timeout in minutes */
  timeout: number;
}

/**
 * Pipeline step
 */
export interface PipelineStep {
  /** Step name */
  name: string;
  /** Step command or action */
  run?: string;
  /** Uses action */
  uses?: string;
  /** Step with */
  with?: Record<string, string>;
  /** Environment variables */
  env?: Record<string, string>;
}

/**
 * Pipeline execution result
 */
export interface PipelineExecutionResult {
  /** Execution ID */
  executionId: string;
  /** Pipeline name */
  pipelineName: string;
  /** Execution status */
  status: 'queued' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  /** Started timestamp */
  startedAt: Date;
  /** Completed timestamp */
  completedAt: Date | null;
  /** Job results */
  jobResults: JobExecutionResult[];
  /** Execution duration in milliseconds */
  duration: number | null;
  /** Execution logs */
  logs: string;
}

/**
 * Job execution result
 */
export interface JobExecutionResult {
  /** Job ID */
  jobId: string;
  /** Job name */
  jobName: string;
  /** Job status */
  status: 'queued' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  /** Started timestamp */
  startedAt: Date;
  /** Completed timestamp */
  completedAt: Date | null;
  /** Step results */
  stepResults: StepExecutionResult[];
  /** Job duration in milliseconds */
  duration: number | null;
  /** Job logs */
  logs: string;
}

/**
 * Step execution result
 */
export interface StepExecutionResult {
  /** Step name */
  stepName: string;
  /** Step status */
  status: 'queued' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  /** Started timestamp */
  startedAt: Date;
  /** Completed timestamp */
  completedAt: Date | null;
  /** Step duration in milliseconds */
  duration: number | null;
  /** Step output */
  output: string;
  /** Step error */
  error: string | null;
}

/**
 * Audit phase result for GitHub integration
 */
export interface AuditPhaseResult {
  /** Phase ID */
  phaseId: string;
  /** Phase name */
  phaseName: string;
  /** Phase status */
  status: 'not_started' | 'in_progress' | 'completed' | 'failed';
  /** Started timestamp */
  startedAt: Date | null;
  /** Completed timestamp */
  completedAt: Date | null;
  /** Phase duration in milliseconds */
  duration: number | null;
  /** Quality metrics */
  qualityMetrics: QualityMetrics;
  /** Phase errors */
  errors: string[];
  /** Phase warnings */
  warnings: string[];
}

/**
 * Quality metrics
 */
export interface QualityMetrics {
  /** Compiler warnings count */
  compilerWarnings: number;
  /** Runtime errors count */
  runtimeErrors: number;
  /** Unused files count */
  unusedFiles: number;
  /** Ambiguous names count */
  ambiguousNames: number;
  /** Test pass rate */
  testPassRate: number;
  /** Code coverage percentage */
  codeCoverage: number;
  /** Property test iterations */
  propertyTestIterations: number;
}

/**
 * GitHub integration error
 */
export class GitHubIntegrationError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode?: number,
    public readonly details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'GitHubIntegrationError';
  }
}

/**
 * API rate limit error
 */
export class RateLimitError extends GitHubIntegrationError {
  constructor(
    message: string,
    public readonly resetAt: Date,
    public readonly remaining: number
  ) {
    super(message, 'RATE_LIMIT_EXCEEDED', 429, { resetAt, remaining });
    this.name = 'RateLimitError';
  }
}

/**
 * Authentication error
 */
export class AuthenticationError extends GitHubIntegrationError {
  constructor(message: string) {
    super(message, 'AUTHENTICATION_FAILED', 401);
    this.name = 'AuthenticationError';
  }
}

/**
 * Validation error
 */
export class ValidationError extends GitHubIntegrationError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, 'VALIDATION_FAILED', 400, details);
    this.name = 'ValidationError';
  }
}

