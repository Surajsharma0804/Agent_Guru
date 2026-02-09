/**
 * GitHub API Integration
 *
 * Comprehensive GitHub API integration with workflow automation and status management.
 * Implements production-grade API client with retry logic, rate limiting, and error handling.
 *
 * MAXIMUM ENGINEERING MANDATE:
 * - Full GitHub API coverage with comprehensive error handling
 * - Zero tolerance for API failures without retry mechanisms
 * - Complete rate limiting and authentication management
 * - 20+ year maintenance lifecycle design
 */

import {
  GitHubConfig,
  GitHubApiResponse,
  CommitInfo,
  PullRequestInfo,
  StatusCheckInfo,
  CheckRunInfo,
  BranchProtectionRules,
  RateLimitInfo,
  GitHubIntegrationError,
  RateLimitError,
  AuthenticationError,
  ValidationError,
} from './types';

/**
 * GitHub API Integration Client
 *
 * Production-grade GitHub API client with comprehensive error handling,
 * automatic retries, rate limiting, and authentication management.
 */
export class GitHubApiIntegration {
  private config: GitHubConfig;
  private rateLimitInfo: RateLimitInfo | null = null;

  constructor(config: GitHubConfig) {
    this.validateConfig(config);
    this.config = config;
  }

  /**
   * Validate configuration
   */
  private validateConfig(config: GitHubConfig): void {
    if (!config.apiUrl) {
      throw new ValidationError('API URL is required');
    }
    if (!config.owner) {
      throw new ValidationError('Repository owner is required');
    }
    if (!config.repo) {
      throw new ValidationError('Repository name is required');
    }
    if (!config.token) {
      throw new ValidationError('Authentication token is required');
    }
    if (config.timeout <= 0) {
      throw new ValidationError('Timeout must be positive');
    }
    if (config.maxRetries < 0) {
      throw new ValidationError('Max retries must be non-negative');
    }
  }

  /**
   * Make API request with retry logic
   */
  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<GitHubApiResponse<T>> {
    const url = `${this.config.apiUrl}${endpoint}`;
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
      try {
        // Check rate limit before making request
        await this.checkRateLimit();

        const response = await fetch(url, {
          ...options,
          headers: {
            'Authorization': `Bearer ${this.config.token}`,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            ...options.headers,
          },
          signal: AbortSignal.timeout(this.config.timeout),
        });

        // Update rate limit information
        this.updateRateLimitInfo(response);

        // Handle authentication errors
        if (response.status === 401 || response.status === 403) {
          throw new AuthenticationError('Authentication failed');
        }

        // Handle rate limit errors
        if (response.status === 429) {
          const resetAt = new Date(
            parseInt(response.headers.get('X-RateLimit-Reset') || '0') * 1000
          );
          const remaining = parseInt(
            response.headers.get('X-RateLimit-Remaining') || '0'
          );
          throw new RateLimitError('Rate limit exceeded', resetAt, remaining);
        }

        // Handle validation errors
        if (response.status === 400 || response.status === 422) {
          const errorData = await response.json();
          throw new ValidationError('Validation failed', errorData);
        }

        // Handle other errors
        if (!response.ok) {
          throw new GitHubIntegrationError(
            `API request failed: ${response.statusText}`,
            'API_REQUEST_FAILED',
            response.status
          );
        }

        const data = await response.json();
        const headers: Record<string, string> = {};
        response.headers.forEach((value, key) => {
          headers[key] = value;
        });

        return {
          data,
          status: response.status,
          headers,
          rateLimit: this.rateLimitInfo!,
        };
      } catch (error) {
        lastError = error as Error;

        // Don't retry on authentication or validation errors
        if (
          error instanceof AuthenticationError ||
          error instanceof ValidationError
        ) {
          throw error;
        }

        // Wait before retrying
        if (attempt < this.config.maxRetries) {
          await this.delay(this.config.retryDelay * Math.pow(2, attempt));
        }
      }
    }

    throw new GitHubIntegrationError(
      `API request failed after ${this.config.maxRetries} retries: ${lastError?.message}`,
      'MAX_RETRIES_EXCEEDED',
      undefined,
      { lastError: lastError?.message }
    );
  }

  /**
   * Update rate limit information from response
   */
  private updateRateLimitInfo(response: Response): void {
    const limit = parseInt(response.headers.get('X-RateLimit-Limit') || '0');
    const remaining = parseInt(
      response.headers.get('X-RateLimit-Remaining') || '0'
    );
    const reset = parseInt(response.headers.get('X-RateLimit-Reset') || '0');

    this.rateLimitInfo = {
      limit,
      remaining,
      reset,
    };
  }

  /**
   * Check rate limit before making request
   */
  private async checkRateLimit(): Promise<void> {
    if (!this.rateLimitInfo) {
      return;
    }

    if (this.rateLimitInfo.remaining === 0) {
      const resetDate = new Date(this.rateLimitInfo.reset * 1000);
      const now = new Date();

      if (resetDate > now) {
        const waitTime = resetDate.getTime() - now.getTime();
        await this.delay(waitTime);
      }
    }
  }

  /**
   * Delay helper
   */
  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Get commit information
   */
  async getCommit(sha: string): Promise<CommitInfo> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/commits/${sha}`;
    const response = await this.makeRequest<any>(endpoint);

    return {
      sha: response.data.sha,
      message: response.data.commit.message,
      author: {
        name: response.data.commit.author.name,
        email: response.data.commit.author.email,
        username: response.data.author?.login,
      },
      committer: {
        name: response.data.commit.committer.name,
        email: response.data.commit.committer.email,
        username: response.data.committer?.login,
      },
      timestamp: new Date(response.data.commit.author.date),
      parents: response.data.parents.map((p: any) => p.sha),
      verification: {
        verified: response.data.commit.verification.verified,
        reason: response.data.commit.verification.reason,
        signature: response.data.commit.verification.signature,
        payload: response.data.commit.verification.payload,
      },
    };
  }

  /**
   * Get pull request information
   */
  async getPullRequest(prNumber: number): Promise<PullRequestInfo> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/pulls/${prNumber}`;
    const response = await this.makeRequest<any>(endpoint);

    return {
      number: response.data.number,
      title: response.data.title,
      body: response.data.body,
      state: response.data.state,
      head: {
        ref: response.data.head.ref,
        sha: response.data.head.sha,
        repo: {
          id: response.data.head.repo.id,
          name: response.data.head.repo.name,
          fullName: response.data.head.repo.full_name,
          owner: {
            name: response.data.head.repo.owner.login,
            email: '',
            username: response.data.head.repo.owner.login,
          },
          url: response.data.head.repo.html_url,
        },
      },
      base: {
        ref: response.data.base.ref,
        sha: response.data.base.sha,
        repo: {
          id: response.data.base.repo.id,
          name: response.data.base.repo.name,
          fullName: response.data.base.repo.full_name,
          owner: {
            name: response.data.base.repo.owner.login,
            email: '',
            username: response.data.base.repo.owner.login,
          },
          url: response.data.base.repo.html_url,
        },
      },
      author: {
        name: response.data.user.login,
        email: '',
        username: response.data.user.login,
      },
      createdAt: new Date(response.data.created_at),
      updatedAt: new Date(response.data.updated_at),
      mergedAt: response.data.merged_at
        ? new Date(response.data.merged_at)
        : null,
      mergeable: response.data.mergeable,
      mergeableState: response.data.mergeable_state,
    };
  }

  /**
   * Create status check
   */
  async createStatusCheck(
    sha: string,
    context: string,
    state: 'pending' | 'success' | 'failure' | 'error',
    description: string,
    targetUrl: string | null = null
  ): Promise<StatusCheckInfo> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/statuses/${sha}`;
    const response = await this.makeRequest<any>(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        state,
        target_url: targetUrl,
        description,
        context,
      }),
    });

    return {
      context: response.data.context,
      state: response.data.state,
      description: response.data.description,
      targetUrl: response.data.target_url,
      createdAt: new Date(response.data.created_at),
      updatedAt: new Date(response.data.updated_at),
    };
  }

  /**
   * Create check run
   */
  async createCheckRun(
    name: string,
    headSha: string,
    status: 'queued' | 'in_progress' | 'completed',
    conclusion:
      | 'success'
      | 'failure'
      | 'neutral'
      | 'cancelled'
      | 'skipped'
      | 'timed_out'
      | 'action_required'
      | null,
    output: {
      title: string;
      summary: string;
      text: string;
    }
  ): Promise<CheckRunInfo> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/check-runs`;
    const response = await this.makeRequest<any>(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        head_sha: headSha,
        status,
        conclusion,
        output,
      }),
    });

    return {
      id: response.data.id,
      name: response.data.name,
      status: response.data.status,
      conclusion: response.data.conclusion,
      startedAt: response.data.started_at
        ? new Date(response.data.started_at)
        : null,
      completedAt: response.data.completed_at
        ? new Date(response.data.completed_at)
        : null,
      output: {
        title: response.data.output.title,
        summary: response.data.output.summary,
        text: response.data.output.text,
        annotations: response.data.output.annotations || [],
      },
      detailsUrl: response.data.details_url,
    };
  }

  /**
   * Update check run
   */
  async updateCheckRun(
    checkRunId: number,
    status: 'queued' | 'in_progress' | 'completed',
    conclusion:
      | 'success'
      | 'failure'
      | 'neutral'
      | 'cancelled'
      | 'skipped'
      | 'timed_out'
      | 'action_required'
      | null,
    output: {
      title: string;
      summary: string;
      text: string;
    }
  ): Promise<CheckRunInfo> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/check-runs/${checkRunId}`;
    const response = await this.makeRequest<any>(endpoint, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        status,
        conclusion,
        output,
      }),
    });

    return {
      id: response.data.id,
      name: response.data.name,
      status: response.data.status,
      conclusion: response.data.conclusion,
      startedAt: response.data.started_at
        ? new Date(response.data.started_at)
        : null,
      completedAt: response.data.completed_at
        ? new Date(response.data.completed_at)
        : null,
      output: {
        title: response.data.output.title,
        summary: response.data.output.summary,
        text: response.data.output.text,
        annotations: response.data.output.annotations || [],
      },
      detailsUrl: response.data.details_url,
    };
  }

  /**
   * Get branch protection rules
   */
  async getBranchProtection(branch: string): Promise<BranchProtectionRules> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/branches/${branch}/protection`;
    const response = await this.makeRequest<any>(endpoint);

    return {
      requiredPullRequestReviews: response.data.required_pull_request_reviews
        ? {
            dismissStaleReviews:
              response.data.required_pull_request_reviews
                .dismiss_stale_reviews,
            requireCodeOwnerReviews:
              response.data.required_pull_request_reviews
                .require_code_owner_reviews,
            requiredApprovingReviewCount:
              response.data.required_pull_request_reviews
                .required_approving_review_count,
          }
        : null,
      requiredStatusChecks: response.data.required_status_checks
        ? {
            strict: response.data.required_status_checks.strict,
            contexts: response.data.required_status_checks.contexts,
          }
        : null,
      enforceAdmins: response.data.enforce_admins.enabled,
      requireLinearHistory: response.data.required_linear_history.enabled,
      allowForcePushes: response.data.allow_force_pushes.enabled,
      allowDeletions: response.data.allow_deletions.enabled,
      requiredSignatures: response.data.required_signatures?.enabled || false,
    };
  }

  /**
   * Update branch protection rules
   */
  async updateBranchProtection(
    branch: string,
    rules: BranchProtectionRules
  ): Promise<void> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/branches/${branch}/protection`;
    await this.makeRequest<any>(endpoint, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        required_pull_request_reviews: rules.requiredPullRequestReviews
          ? {
              dismiss_stale_reviews:
                rules.requiredPullRequestReviews.dismissStaleReviews,
              require_code_owner_reviews:
                rules.requiredPullRequestReviews.requireCodeOwnerReviews,
              required_approving_review_count:
                rules.requiredPullRequestReviews.requiredApprovingReviewCount,
            }
          : null,
        required_status_checks: rules.requiredStatusChecks
          ? {
              strict: rules.requiredStatusChecks.strict,
              contexts: rules.requiredStatusChecks.contexts,
            }
          : null,
        enforce_admins: rules.enforceAdmins,
        required_linear_history: rules.requireLinearHistory,
        allow_force_pushes: rules.allowForcePushes,
        allow_deletions: rules.allowDeletions,
        required_signatures: rules.requiredSignatures,
      }),
    });
  }

  /**
   * Trigger workflow dispatch
   */
  async triggerWorkflowDispatch(
    workflowId: string,
    ref: string,
    inputs: Record<string, string> = {}
  ): Promise<void> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/actions/workflows/${workflowId}/dispatches`;
    await this.makeRequest<any>(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ref,
        inputs,
      }),
    });
  }

  /**
   * Get workflow run
   */
  async getWorkflowRun(runId: number): Promise<any> {
    const endpoint = `/repos/${this.config.owner}/${this.config.repo}/actions/runs/${runId}`;
    const response = await this.makeRequest<any>(endpoint);
    return response.data;
  }

  /**
   * List workflow runs
   */
  async listWorkflowRuns(
    workflowId: string,
    branch?: string,
    status?: string
  ): Promise<any[]> {
    let endpoint = `/repos/${this.config.owner}/${this.config.repo}/actions/workflows/${workflowId}/runs`;
    const params = new URLSearchParams();

    if (branch) {
      params.append('branch', branch);
    }
    if (status) {
      params.append('status', status);
    }

    if (params.toString()) {
      endpoint += `?${params.toString()}`;
    }

    const response = await this.makeRequest<any>(endpoint);
    return response.data.workflow_runs;
  }

  /**
   * Get rate limit information
   */
  getRateLimitInfo(): RateLimitInfo | null {
    return this.rateLimitInfo;
  }
}

