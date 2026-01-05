/**
 * GURU Personal Assistant - Security Test Results Processor
 * 
 * Processes test results with a focus on security test outcomes
 * and generates security-focused reports.
 */

const fs = require('fs');
const path = require('path');

module.exports = (results) => {
  const securityReport = {
    timestamp: new Date().toISOString(),
    summary: {
      totalTests: results.numTotalTests,
      passedTests: results.numPassedTests,
      failedTests: results.numFailedTests,
      securityTests: 0,
      securityFailures: 0
    },
    securityResults: [],
    recommendations: []
  };

  // Process test results to identify security-related tests
  if (results.testResults) {
    results.testResults.forEach(testResult => {
      if (testResult.assertionResults) {
        testResult.assertionResults.forEach(assertion => {
      const isSecurityTest = 
        assertion.title.toLowerCase().includes('security') ||
        assertion.ancestorTitles.some(title => 
          title.toLowerCase().includes('security') ||
          title.toLowerCase().includes('permission') ||
          title.toLowerCase().includes('validation')
        );

      if (isSecurityTest) {
        securityReport.summary.securityTests++;
        
        if (assertion.status === 'failed') {
          securityReport.summary.securityFailures++;
          
          securityReport.securityResults.push({
            test: assertion.title,
            suite: assertion.ancestorTitles.join(' > '),
            status: 'FAILED',
            message: assertion.failureMessages?.[0] || 'Unknown failure',
            severity: determineSeverity(assertion.title, assertion.failureMessages?.[0])
          });
        } else if (assertion.status === 'passed') {
          securityReport.securityResults.push({
            test: assertion.title,
            suite: assertion.ancestorTitles.join(' > '),
            status: 'PASSED',
            severity: 'INFO'
          });
        }
      }
    });
      }
    });
  }

  // Generate security recommendations
  generateSecurityRecommendations(securityReport);

  // Write security report
  const reportPath = path.join(process.cwd(), 'coverage', 'security-report.json');
  const reportDir = path.dirname(reportPath);
  
  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true });
  }
  
  fs.writeFileSync(reportPath, JSON.stringify(securityReport, null, 2));

  // Console output for security results
  console.log('\n' + '='.repeat(60));
  console.log('🔒 SECURITY TEST RESULTS');
  console.log('='.repeat(60));
  
  console.log(`Total Security Tests: ${securityReport.summary.securityTests}`);
  console.log(`Security Failures: ${securityReport.summary.securityFailures}`);
  
  if (securityReport.summary.securityFailures > 0) {
    console.log('\n❌ SECURITY TEST FAILURES:');
    securityReport.securityResults
      .filter(result => result.status === 'FAILED')
      .forEach(result => {
        console.log(`  • [${result.severity}] ${result.suite} > ${result.test}`);
        if (result.message) {
          console.log(`    ${result.message.split('\n')[0]}`);
        }
      });
  } else {
    console.log('\n✅ All security tests passed!');
  }

  if (securityReport.recommendations.length > 0) {
    console.log('\n💡 SECURITY RECOMMENDATIONS:');
    securityReport.recommendations.forEach(rec => {
      console.log(`  • ${rec}`);
    });
  }

  console.log('='.repeat(60));
  console.log(`📊 Security report saved to: ${reportPath}`);

  return results;
};

/**
 * Determine the severity of a security test failure
 */
function determineSeverity(testTitle, failureMessage) {
  const title = testTitle.toLowerCase();
  const message = (failureMessage || '').toLowerCase();

  // Critical security issues
  if (title.includes('world-writable') || 
      title.includes('permission') ||
      message.includes('security risk')) {
    return 'CRITICAL';
  }

  // High priority security issues
  if (title.includes('cryptographic') ||
      title.includes('authentication') ||
      title.includes('authorization')) {
    return 'HIGH';
  }

  // Medium priority security issues
  if (title.includes('validation') ||
      title.includes('sanitization') ||
      title.includes('configuration')) {
    return 'MEDIUM';
  }

  // Default to low priority
  return 'LOW';
}

/**
 * Generate security recommendations based on test results
 */
function generateSecurityRecommendations(report) {
  const failures = report.securityResults.filter(r => r.status === 'FAILED');
  
  // Permission-related recommendations
  const permissionFailures = failures.filter(f => 
    f.test.toLowerCase().includes('permission') ||
    f.message.toLowerCase().includes('world-writable')
  );
  
  if (permissionFailures.length > 0) {
    report.recommendations.push(
      'Review and fix file permissions - avoid world-writable files'
    );
  }

  // Configuration-related recommendations
  const configFailures = failures.filter(f =>
    f.test.toLowerCase().includes('configuration') ||
    f.test.toLowerCase().includes('gitignore')
  );
  
  if (configFailures.length > 0) {
    report.recommendations.push(
      'Update security configuration files to include all required patterns'
    );
  }

  // Structure-related recommendations
  const structureFailures = failures.filter(f =>
    f.test.toLowerCase().includes('structure') ||
    f.test.toLowerCase().includes('directory')
  );
  
  if (structureFailures.length > 0) {
    report.recommendations.push(
      'Ensure all required directories and files are present'
    );
  }

  // Critical security recommendations
  const criticalFailures = failures.filter(f => f.severity === 'CRITICAL');
  
  if (criticalFailures.length > 0) {
    report.recommendations.push(
      'URGENT: Address critical security failures before deployment'
    );
  }

  // General recommendations
  if (failures.length > 0) {
    report.recommendations.push(
      'Run security validation scripts before committing changes'
    );
  }
}