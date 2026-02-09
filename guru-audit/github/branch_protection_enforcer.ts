/**
 * Branch Protection Enforcer
 *
 * Comprehensive branch protection enforcement with required checks and merge prevention.
 * Implements production-grade protection rules with zero-tolerance policy enforcement.
 *
 * MAXIMUM ENGINEERING MANDATE:
 * - Full branch protection with comprehensive rule enforcement
 * - Zero tolerance for unprotected branches or bypassed checks
 * - Complete merge prevention and status validation
 * - 20+ year maintenance lifecycle design
 */

import { GitHubApiIntegration } from './api_integration';
import {
  BranchProtectionRules,
  PullRequestInfo,
  StatusCheckInfo,
  GitHubIntegrationError,
  ValidationError,
} from './types';

/**
 * Branch Protection Enforcer
 *
 * Production-grade branch protection enforcer with comprehensive rule validation,
 * merge prevention, and status check enforcement.
 */
export class BranchProtectionEnforcer {
  private apiClient: GitHubApiIntegration;
  private protectedBranches: Map<string, BranchProtectionRules> = new Map();

  constructor(apiClient: GitHubApiIntegration) {
    this.apiClient = apiClient;
  }

  /**
   * Enforce branch protection rules
   */
  async enforceBranchProtection(
    branch: string,
    rules: BranchProtectionRules
  ): Promise<void> {
    try {
      // Validate rules
      this.validateProtectionRules(rules);

      // Update branch protection
      await this.apiClient.updateBranchProtection(branch, rules);

      // Cache protection rules
      this.protectedBranches.set(branch, rules);
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to enforce branch protection: ${error instanceof Error ? error.message : String(error)}`,
        'BRANCH_PROTECTION_FAILED',
        undefined,
        { branch, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Validate protection rules
   */
  private validateProtectionRules(rules: BranchProtectionRules): void {
    // Validate required pull request reviews
    if (rules.requiredPullRequestReviews) {
      if (rules.requiredPullRequestReviews.requiredApprovingReviewCount < 0) {
        throw new ValidationError(
          'Required approving review count must be non-negative'
        );
      }
    }

    // Validate required status checks
    if (rules.requiredStatusChecks) {
      if (rules.requiredStatusChecks.contexts.length === 0) {
        throw new ValidationError(
          'At least one required status check context must be specified'
        );
      }
    }

    // Enforce audit system requirements
    if (!rules.requiredStatusChecks) {
      throw new ValidationError(
        'Required status checks must be enabled for audit system'
      );
    }

    if (!rules.requiredSignatures) {
      throw new ValidationError(
        'Required signatures must be enabled for audit system'
      );
    }

    if (rules.allowForcePushes) {
      throw new ValidationError(
        'Force pushes must be disabled for audit system'
      );
    }
  }

  /**
   * Check if merge is allowed
   */
  async checkMergeAllowed(prNumber: number): Promise<{
    allowed: boolean;
    reasons: string[];
  }> {
    const reasons: string[] = [];

    try {
      // Get pull request information
      const pr = await this.apiClient.getPullRequest(prNumber);

      // Check if PR is mergeable
      if (!pr.mergeable) {
        reasons.push('Pull request has merge conflicts');
      }

      // Get branch protection rules
      const protection = await this.apiClient.getBranchProtection(
        pr.base.ref
      );

      // Check required status checks
      if (protection.requiredStatusChecks) {
        const statusChecks = await this.getStatusChecks(pr.head.sha);
        const missingChecks = this.findMissingStatusChecks(
          protection.requiredStatusChecks.contexts,
          statusChecks
        );

        if (missingChecks.length > 0) {
          reasons.push(
            `Missing required status checks: ${missingChecks.join(', ')}`
          );
        }

        const failedChecks = statusChecks.filter(
          (check) => check.state === 'failure' || check.state === 'error'
        );

        if (failedChecks.length > 0) {
          reasons.push(
            `Failed status checks: ${failedChecks.map((c) => c.context).join(', ')}`
          );
        }
      }

      // Check required pull request reviews
      if (protection.requiredPullRequestReviews) {
        const reviews = await this.getPullRequestReviews(prNumber);
        const approvedReviews = reviews.filter(
          (review) => review.state === 'APPROVED'
        );

        if (
          approvedReviews.length <
          protection.requiredPullRequestReviews.requiredApprovingReviewCount
        ) {
          reasons.push(
            `Insufficient approving reviews: ${approvedReviews.length}/${protection.requiredPullRequestReviews.requiredApprovingReviewCount} required`
          );
        }
      }

      // Check commit signature verification
      if (protection.requiredSignatures) {
        const commit = await this.apiClient.getCommit(pr.head.sha);
        if (!commit.verification.verified) {
          reasons.push(
            `Commit signature not verified: ${commit.verification.reason}`
          );
        }
      }

      return {
        allowed: reasons.length === 0,
        reasons,
      };
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to check merge allowed: ${error instanceof Error ? error.message : String(error)}`,
        'MERGE_CHECK_FAILED',
        undefined,
        { prNumber, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Get status checks for commit
   */
  private async getStatusChecks(sha: string): Promise<StatusCheckInfo[]> {
    // This would need to be implemented with actual GitHub API call
    // For now, return empty array as placeholder
    return [];
  }

  /**
   * Get pull request reviews
   */
  private async getPullRequestReviews(prNumber: number): Promise<any[]> {
    // This would need to be implemented with actual GitHub API call
    // For now, return empty array as placeholder
    return [];
  }

  /**
   * Find missing status checks
   */
  private findMissingStatusChecks(
    required: string[],
    actual: StatusCheckInfo[]
  ): string[] {
    const actualContexts = new Set(actual.map((check) => check.context));
    return required.filter((context) => !actualContexts.has(context));
  }

  /**
   * Block merge
   */
  async blockMerge(
    prNumber: number,
    reason: string
  ): Promise<void> {
    try {
      const pr = await this.apiClient.getPullRequest(prNumber);

      // Create failing status check to block merge
      await this.apiClient.createStatusCheck(
        pr.head.sha,
        'audit-system/merge-blocker',
        'failure',
        `Merge blocked: ${reason}`,
        null
      );
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to block merge: ${error instanceof Error ? error.message : String(error)}`,
        'MERGE_BLOCK_FAILED',
        undefined,
        { prNumber, reason, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Allow merge
   */
  async allowMerge(prNumber: number): Promise<void> {
    try {
      const pr = await this.apiClient.getPullRequest(prNumber);

      // Create successful status check to allow merge
      await this.apiClient.createStatusCheck(
        pr.head.sha,
        'audit-system/merge-blocker',
        'success',
        'All audit checks passed - merge allowed',
        null
      );
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to allow merge: ${error instanceof Error ? error.message : String(error)}`,
        'MERGE_ALLOW_FAILED',
        undefined,
        { prNumber, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Get protected branches
   */
  getProtectedBranches(): Map<string, BranchProtectionRules> {
    return new Map(this.protectedBranches);
  }

  /**
   * Check if branch is protected
   */
  isBranchProtected(branch: string): boolean {
    return this.protectedBranches.has(branch);
  }

  /**
   * Get protection rules for branch
   */
  getProtectionRules(branch: string): BranchProtectionRules | undefined {
    return this.protectedBranches.get(branch);
  }

  /**
   * Enforce audit system protection rules
   */
  async enforceAuditSystemProtection(branch: string): Promise<void> {
    const rules: BranchProtectionRules = {
      requiredPullRequestReviews: {
        dismissStaleReviews: true,
        requireCodeOwnerReviews: true,
        requiredApprovingReviewCount: 2,
      },
      requiredStatusChecks: {
        strict: true,
        contexts: [
          'audit-system/phase-1-inventory',
          'audit-system/phase-2-naming',
          'audit-system/phase-3-purge',
          'audit-system/phase-4-integration',
          'audit-system/phase-5-testing',
          'audit-system/phase-6-performance',
          'audit-system/phase-7-formal',
          'audit-system/phase-8-build',
          'audit-system/phase-9-runtime',
          'audit-system/phase-10-certification',
        ],
      },
      enforceAdmins: true,
      requireLinearHistory: true,
      allowForcePushes: false,
      allowDeletions: false,
      requiredSignatures: true,
    };

    await this.enforceBranchProtection(branch, rules);
  }
}

