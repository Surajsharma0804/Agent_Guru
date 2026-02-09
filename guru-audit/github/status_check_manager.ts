/**
 * Status Check Manager
 *
 * Comprehensive status check management with real-time updates and failure notification.
 * Implements production-grade status tracking with complete audit phase integration.
 *
 * MAXIMUM ENGINEERING MANDATE:
 * - Full status check lifecycle management with real-time updates
 * - Zero tolerance for missed status updates or notification failures
 * - Complete audit phase integration and result reporting
 * - 20+ year maintenance lifecycle design
 */

import { GitHubApiIntegration } from './api_integration';
import {
  StatusCheckInfo,
  CheckRunInfo,
  AuditPhaseResult,
  GitHubIntegrationError,
} from './types';

/**
 * Status Check Manager
 *
 * Production-grade status check manager with comprehensive lifecycle management,
 * real-time updates, and failure notification.
 */
export class StatusCheckManager {
  private apiClient: GitHubApiIntegration;
  private activeChecks: Map<string, CheckRunInfo> = new Map();

  constructor(apiClient: GitHubApiIntegration) {
    this.apiClient = apiClient;
  }

  /**
   * Create audit phase status check
   */
  async createAuditPhaseCheck(
    phaseId: string,
    phaseName: string,
    sha: string
  ): Promise<CheckRunInfo> {
    try {
      const checkRun = await this.apiClient.createCheckRun(
        `audit-system/phase-${phaseId}-${phaseName}`,
        sha,
        'queued',
        null,
        {
          title: `Audit Phase ${phaseId}: ${phaseName}`,
          summary: `Executing audit phase ${phaseId}...`,
          text: `Phase ${phaseName} is queued for execution.`,
        }
      );

      this.activeChecks.set(checkRun.id.toString(), checkRun);
      return checkRun;
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to create audit phase check: ${error instanceof Error ? error.message : String(error)}`,
        'CHECK_CREATION_FAILED',
        undefined,
        { phaseId, phaseName, sha, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Update audit phase check to in progress
   */
  async updateCheckInProgress(
    checkRunId: number,
    phaseId: string,
    phaseName: string
  ): Promise<CheckRunInfo> {
    try {
      const checkRun = await this.apiClient.updateCheckRun(
        checkRunId,
        'in_progress',
        null,
        {
          title: `Audit Phase ${phaseId}: ${phaseName}`,
          summary: `Executing audit phase ${phaseId}...`,
          text: `Phase ${phaseName} is currently executing.`,
        }
      );

      this.activeChecks.set(checkRun.id.toString(), checkRun);
      return checkRun;
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to update check to in progress: ${error instanceof Error ? error.message : String(error)}`,
        'CHECK_UPDATE_FAILED',
        undefined,
        { checkRunId, phaseId, phaseName, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Update audit phase check with result
   */
  async updateCheckWithResult(
    checkRunId: number,
    result: AuditPhaseResult
  ): Promise<CheckRunInfo> {
    try {
      const conclusion =
        result.status === 'completed' ? 'success' : 'failure';
      const summary = this.generateResultSummary(result);
      const text = this.generateResultText(result);

      const checkRun = await this.apiClient.updateCheckRun(
        checkRunId,
        'completed',
        conclusion,
        {
          title: `Audit Phase ${result.phaseId}: ${result.phaseName}`,
          summary,
          text,
        }
      );

      this.activeChecks.delete(checkRun.id.toString());
      return checkRun;
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to update check with result: ${error instanceof Error ? error.message : String(error)}`,
        'CHECK_UPDATE_FAILED',
        undefined,
        { checkRunId, result, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Generate result summary
   */
  private generateResultSummary(result: AuditPhaseResult): string {
    if (result.status === 'completed') {
      return `✅ Phase ${result.phaseId} completed successfully in ${result.duration}ms`;
    } else {
      return `❌ Phase ${result.phaseId} failed after ${result.duration}ms`;
    }
  }

  /**
   * Generate result text
   */
  private generateResultText(result: AuditPhaseResult): string {
    let text = `## Audit Phase ${result.phaseId}: ${result.phaseName}\n\n`;

    text += `**Status:** ${result.status}\n`;
    text += `**Duration:** ${result.duration}ms\n\n`;

    text += `### Quality Metrics\n\n`;
    text += `- Compiler Warnings: ${result.qualityMetrics.compilerWarnings}\n`;
    text += `- Runtime Errors: ${result.qualityMetrics.runtimeErrors}\n`;
    text += `- Unused Files: ${result.qualityMetrics.unusedFiles}\n`;
    text += `- Ambiguous Names: ${result.qualityMetrics.ambiguousNames}\n`;
    text += `- Test Pass Rate: ${result.qualityMetrics.testPassRate}%\n`;
    text += `- Code Coverage: ${result.qualityMetrics.codeCoverage}%\n`;
    text += `- Property Test Iterations: ${result.qualityMetrics.propertyTestIterations}\n\n`;

    if (result.errors.length > 0) {
      text += `### Errors\n\n`;
      for (const error of result.errors) {
        text += `- ${error}\n`;
      }
      text += `\n`;
    }

    if (result.warnings.length > 0) {
      text += `### Warnings\n\n`;
      for (const warning of result.warnings) {
        text += `- ${warning}\n`;
      }
      text += `\n`;
    }

    return text;
  }

  /**
   * Create status check for commit
   */
  async createStatusCheck(
    sha: string,
    context: string,
    state: 'pending' | 'success' | 'failure' | 'error',
    description: string,
    targetUrl: string | null = null
  ): Promise<StatusCheckInfo> {
    try {
      return await this.apiClient.createStatusCheck(
        sha,
        context,
        state,
        description,
        targetUrl
      );
    } catch (error) {
      throw new GitHubIntegrationError(
        `Failed to create status check: ${error instanceof Error ? error.message : String(error)}`,
        'STATUS_CHECK_FAILED',
        undefined,
        { sha, context, state, description, error: error instanceof Error ? error.message : String(error) }
      );
    }
  }

  /**
   * Get active checks
   */
  getActiveChecks(): CheckRunInfo[] {
    return Array.from(this.activeChecks.values());
  }

  /**
   * Get check by ID
   */
  getCheck(checkRunId: string): CheckRunInfo | undefined {
    return this.activeChecks.get(checkRunId);
  }

  /**
   * Clear completed checks
   */
  clearCompletedChecks(): void {
    for (const [id, check] of this.activeChecks.entries()) {
      if (check.status === 'completed') {
        this.activeChecks.delete(id);
      }
    }
  }
}

