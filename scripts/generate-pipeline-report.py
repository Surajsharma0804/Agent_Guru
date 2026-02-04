#!/usr/bin/env python3

"""
AGENT_GURU Pipeline Report Generator
Enterprise-grade CI/CD pipeline reporting with comprehensive analytics
Zero-tolerance quality standards with maximum visibility
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import subprocess
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PipelineReportGenerator:
    """Enterprise-grade pipeline report generator with comprehensive analytics."""
    
    def __init__(self):
        self.report_data = {
            'metadata': {
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'generator_version': '1.0.0',
                'pipeline_id': os.getenv('CI_PIPELINE_ID', 'local'),
                'commit_sha': self._get_git_commit(),
                'branch': self._get_git_branch(),
                'environment': os.getenv('CI_ENVIRONMENT_NAME', 'unknown')
            },
            'summary': {
                'overall_status': 'UNKNOWN',
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'coverage_percentage': 0.0,
                'security_issues': 0,
                'performance_regressions': 0,
                'quality_score': 0.0
            },
            'details': {
                'build': {},
                'tests': {},
                'coverage': {},
                'security': {},
                'performance': {},
                'quality': {}
            },
            'artifacts': [],
            'recommendations': []
        }
    
    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return 'unknown'
    
    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return 'unknown'
    
    def process_coverage_report(self, coverage_file: Path):
        """Process coverage report and extract metrics."""
        logger.info(f"Processing coverage report: {coverage_file}")
        
        if not coverage_file.exists():
            logger.warning(f"Coverage file not found: {coverage_file}")
            return
        
        try:
            if coverage_file.suffix == '.xml':
                self._process_xml_coverage(coverage_file)
            elif coverage_file.suffix == '.json':
                self._process_json_coverage(coverage_file)
            else:
                logger.warning(f"Unsupported coverage format: {coverage_file}")
        except Exception as e:
            logger.error(f"Failed to process coverage report: {e}")
    
    def _process_xml_coverage(self, xml_file: Path):
        """Process XML coverage report (Cobertura format)."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        line_coverage = float(root.get('line-rate', 0)) * 100
        branch_coverage = float(root.get('branch-rate', 0)) * 100
        
        self.report_data['summary']['coverage_percentage'] = line_coverage
        self.report_data['details']['coverage'] = {
            'line_coverage': line_coverage,
            'branch_coverage': branch_coverage,
            'format': 'cobertura',
            'source_file': str(xml_file)
        }
        
        # Extract package-level details
        packages = []
        for package in root.findall('.//package'):
            package_data = {
                'name': package.get('name', 'unknown'),
                'line_coverage': float(package.get('line-rate', 0)) * 100,
                'branch_coverage': float(package.get('branch-rate', 0)) * 100,
                'classes': len(package.findall('.//class'))
            }
            packages.append(package_data)
        
        self.report_data['details']['coverage']['packages'] = packages
    
    def _process_json_coverage(self, json_file: Path):
        """Process JSON coverage report."""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON formats
        if 'totals' in data:
            coverage = data['totals'].get('percent_covered', 0)
        elif 'summary' in data:
            coverage = data['summary'].get('line_coverage', 0)
        else:
            coverage = 0
        
        self.report_data['summary']['coverage_percentage'] = coverage
        self.report_data['details']['coverage'] = {
            'line_coverage': coverage,
            'format': 'json',
            'source_file': str(json_file),
            'raw_data': data
        }
    
    def process_security_report(self, security_dir: Path):
        """Process security scan reports."""
        logger.info(f"Processing security reports from: {security_dir}")
        
        if not security_dir.exists():
            logger.warning(f"Security directory not found: {security_dir}")
            return
        
        security_data = {
            'total_issues': 0,
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0,
            'reports': []
        }
        
        # Process SARIF files
        for sarif_file in security_dir.glob('*.sarif'):
            try:
                with open(sarif_file, 'r') as f:
                    sarif_data = json.load(f)
                
                for run in sarif_data.get('runs', []):
                    results = run.get('results', [])
                    for result in results:
                        security_data['total_issues'] += 1
                        
                        # Categorize by severity
                        level = result.get('level', 'info')
                        if level == 'error':
                            security_data['high_severity'] += 1
                        elif level == 'warning':
                            security_data['medium_severity'] += 1
                        else:
                            security_data['low_severity'] += 1
                
                security_data['reports'].append({
                    'file': str(sarif_file),
                    'format': 'sarif',
                    'issues': len(results)
                })
                
            except Exception as e:
                logger.error(f"Failed to process SARIF file {sarif_file}: {e}")
        
        # Process other security report formats
        for json_file in security_dir.glob('*-security.json'):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract issue counts based on common formats
                if 'vulnerabilities' in data:
                    issues = len(data['vulnerabilities'])
                    security_data['total_issues'] += issues
                    security_data['high_severity'] += issues  # Assume high severity
                
                security_data['reports'].append({
                    'file': str(json_file),
                    'format': 'json',
                    'issues': issues
                })
                
            except Exception as e:
                logger.error(f"Failed to process security JSON file {json_file}: {e}")
        
        self.report_data['summary']['security_issues'] = security_data['total_issues']
        self.report_data['details']['security'] = security_data
    
    def process_performance_report(self, performance_dir: Path):
        """Process performance benchmark reports."""
        logger.info(f"Processing performance reports from: {performance_dir}")
        
        if not performance_dir.exists():
            logger.warning(f"Performance directory not found: {performance_dir}")
            return
        
        performance_data = {
            'benchmarks': [],
            'regressions': 0,
            'improvements': 0,
            'total_benchmarks': 0
        }
        
        # Process Criterion benchmark results
        criterion_dir = performance_dir / 'criterion-results'
        if criterion_dir.exists():
            for benchmark_dir in criterion_dir.iterdir():
                if benchmark_dir.is_dir():
                    estimates_file = benchmark_dir / 'base' / 'estimates.json'
                    if estimates_file.exists():
                        try:
                            with open(estimates_file, 'r') as f:
                                estimates = json.load(f)
                            
                            benchmark_data = {
                                'name': benchmark_dir.name,
                                'mean_time_ns': estimates.get('mean', {}).get('point_estimate', 0),
                                'std_dev_ns': estimates.get('std_dev', {}).get('point_estimate', 0),
                                'median_time_ns': estimates.get('median', {}).get('point_estimate', 0)
                            }
                            
                            performance_data['benchmarks'].append(benchmark_data)
                            performance_data['total_benchmarks'] += 1
                            
                        except Exception as e:
                            logger.error(f"Failed to process benchmark {benchmark_dir}: {e}")
        
        # Process other performance reports
        for json_file in performance_dir.glob('*-performance.json'):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract performance metrics
                if 'regressions' in data:
                    performance_data['regressions'] += len(data['regressions'])
                if 'improvements' in data:
                    performance_data['improvements'] += len(data['improvements'])
                
            except Exception as e:
                logger.error(f"Failed to process performance JSON file {json_file}: {e}")
        
        self.report_data['summary']['performance_regressions'] = performance_data['regressions']
        self.report_data['details']['performance'] = performance_data
    
    def process_test_results(self, test_files: List[Path]):
        """Process test result files."""
        logger.info("Processing test results")
        
        test_data = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'test_suites': []
        }
        
        for test_file in test_files:
            if not test_file.exists():
                logger.warning(f"Test file not found: {test_file}")
                continue
            
            try:
                if test_file.suffix == '.xml':
                    self._process_junit_xml(test_file, test_data)
                elif test_file.suffix == '.json':
                    self._process_json_test_results(test_file, test_data)
            except Exception as e:
                logger.error(f"Failed to process test file {test_file}: {e}")
        
        self.report_data['summary']['total_tests'] = test_data['total_tests']
        self.report_data['summary']['passed_tests'] = test_data['passed_tests']
        self.report_data['summary']['failed_tests'] = test_data['failed_tests']
        self.report_data['details']['tests'] = test_data
    
    def _process_junit_xml(self, xml_file: Path, test_data: Dict):
        """Process JUnit XML test results."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        suite_data = {
            'name': root.get('name', str(xml_file)),
            'tests': int(root.get('tests', 0)),
            'failures': int(root.get('failures', 0)),
            'errors': int(root.get('errors', 0)),
            'skipped': int(root.get('skipped', 0)),
            'time': float(root.get('time', 0))
        }
        
        test_data['total_tests'] += suite_data['tests']
        test_data['failed_tests'] += suite_data['failures'] + suite_data['errors']
        test_data['skipped_tests'] += suite_data['skipped']
        test_data['passed_tests'] += (
            suite_data['tests'] - suite_data['failures'] - 
            suite_data['errors'] - suite_data['skipped']
        )
        
        test_data['test_suites'].append(suite_data)
    
    def _process_json_test_results(self, json_file: Path, test_data: Dict):
        """Process JSON test results."""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON test result formats
        if 'summary' in data:
            summary = data['summary']
            suite_data = {
                'name': str(json_file),
                'tests': summary.get('total', 0),
                'failures': summary.get('failed', 0),
                'errors': summary.get('error', 0),
                'skipped': summary.get('skipped', 0),
                'passed': summary.get('passed', 0)
            }
        else:
            # Fallback format
            suite_data = {
                'name': str(json_file),
                'tests': data.get('total_tests', 0),
                'failures': data.get('failed_tests', 0),
                'errors': 0,
                'skipped': data.get('skipped_tests', 0),
                'passed': data.get('passed_tests', 0)
            }
        
        test_data['total_tests'] += suite_data['tests']
        test_data['failed_tests'] += suite_data['failures'] + suite_data['errors']
        test_data['skipped_tests'] += suite_data['skipped']
        test_data['passed_tests'] += suite_data['passed']
        
        test_data['test_suites'].append(suite_data)
    
    def calculate_quality_score(self):
        """Calculate overall quality score based on metrics."""
        score = 100.0
        
        # Coverage impact (30% weight)
        coverage = self.report_data['summary']['coverage_percentage']
        if coverage < 100:
            score -= (100 - coverage) * 0.3
        
        # Test failure impact (40% weight)
        total_tests = self.report_data['summary']['total_tests']
        failed_tests = self.report_data['summary']['failed_tests']
        if total_tests > 0:
            failure_rate = failed_tests / total_tests
            score -= failure_rate * 40
        
        # Security issues impact (20% weight)
        security_issues = self.report_data['summary']['security_issues']
        if security_issues > 0:
            score -= min(security_issues * 5, 20)  # Cap at 20 points
        
        # Performance regressions impact (10% weight)
        regressions = self.report_data['summary']['performance_regressions']
        if regressions > 0:
            score -= min(regressions * 2, 10)  # Cap at 10 points
        
        self.report_data['summary']['quality_score'] = max(0, score)
    
    def determine_overall_status(self):
        """Determine overall pipeline status."""
        failed_tests = self.report_data['summary']['failed_tests']
        security_issues = self.report_data['summary']['security_issues']
        coverage = self.report_data['summary']['coverage_percentage']
        quality_score = self.report_data['summary']['quality_score']
        
        if failed_tests > 0:
            status = 'FAILED'
        elif security_issues > 0:
            status = 'FAILED'
        elif coverage < 100:
            status = 'FAILED'
        elif quality_score < 95:
            status = 'WARNING'
        else:
            status = 'PASSED'
        
        self.report_data['summary']['overall_status'] = status
    
    def generate_recommendations(self):
        """Generate actionable recommendations based on results."""
        recommendations = []
        
        # Coverage recommendations
        coverage = self.report_data['summary']['coverage_percentage']
        if coverage < 100:
            recommendations.append({
                'category': 'coverage',
                'priority': 'high',
                'message': f'Increase code coverage from {coverage:.1f}% to 100%',
                'action': 'Add tests for uncovered code paths'
            })
        
        # Test failure recommendations
        failed_tests = self.report_data['summary']['failed_tests']
        if failed_tests > 0:
            recommendations.append({
                'category': 'tests',
                'priority': 'critical',
                'message': f'Fix {failed_tests} failing tests',
                'action': 'Review test failures and fix underlying issues'
            })
        
        # Security recommendations
        security_issues = self.report_data['summary']['security_issues']
        if security_issues > 0:
            recommendations.append({
                'category': 'security',
                'priority': 'critical',
                'message': f'Address {security_issues} security issues',
                'action': 'Review security scan results and apply fixes'
            })
        
        # Performance recommendations
        regressions = self.report_data['summary']['performance_regressions']
        if regressions > 0:
            recommendations.append({
                'category': 'performance',
                'priority': 'medium',
                'message': f'Address {regressions} performance regressions',
                'action': 'Review benchmark results and optimize slow code paths'
            })
        
        self.report_data['recommendations'] = recommendations
    
    def generate_html_report(self, output_file: Path):
        """Generate HTML report."""
        logger.info(f"Generating HTML report: {output_file}")
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AGENT_GURU Pipeline Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .status-passed {{ color: #27ae60; font-weight: bold; }}
        .status-failed {{ color: #e74c3c; font-weight: bold; }}
        .status-warning {{ color: #f39c12; font-weight: bold; }}
        .metric-card {{ background-color: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #3498db; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ color: #7f8c8d; font-size: 14px; }}
        .recommendations {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .recommendation {{ margin: 10px 0; padding: 10px; background-color: white; border-radius: 3px; }}
        .priority-critical {{ border-left: 4px solid #e74c3c; }}
        .priority-high {{ border-left: 4px solid #f39c12; }}
        .priority-medium {{ border-left: 4px solid #3498db; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .progress-bar {{ width: 100%; height: 20px; background-color: #ecf0f1; border-radius: 10px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background-color: #27ae60; transition: width 0.3s ease; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AGENT_GURU Pipeline Report</h1>
            <p>Generated: {self.report_data['metadata']['generated_at']}</p>
            <p>Pipeline ID: {self.report_data['metadata']['pipeline_id']}</p>
            <p>Commit: {self.report_data['metadata']['commit_sha'][:8]}</p>
            <p>Branch: {self.report_data['metadata']['branch']}</p>
        </div>
        
        <div class="summary">
            <h2>📊 Pipeline Summary</h2>
            <p class="status-{self.report_data['summary']['overall_status'].lower()}">
                Overall Status: {self.report_data['summary']['overall_status']}
            </p>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div class="metric-card">
                    <div class="metric-value">{self.report_data['summary']['quality_score']:.1f}%</div>
                    <div class="metric-label">Quality Score</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.report_data['summary']['coverage_percentage']:.1f}%</div>
                    <div class="metric-label">Code Coverage</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.report_data['summary']['passed_tests']}/{self.report_data['summary']['total_tests']}</div>
                    <div class="metric-label">Tests Passed</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{self.report_data['summary']['security_issues']}</div>
                    <div class="metric-label">Security Issues</div>
                </div>
            </div>
        </div>
        
        <div class="details">
            <h2>📋 Detailed Results</h2>
            
            <h3>🧪 Test Results</h3>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {(self.report_data['summary']['passed_tests'] / max(self.report_data['summary']['total_tests'], 1)) * 100}%"></div>
            </div>
            <p>{self.report_data['summary']['passed_tests']} passed, {self.report_data['summary']['failed_tests']} failed, {self.report_data['summary']['total_tests']} total</p>
            
            <h3>🔒 Security Analysis</h3>
            <p>Total Issues: {self.report_data['summary']['security_issues']}</p>
            
            <h3>⚡ Performance Analysis</h3>
            <p>Performance Regressions: {self.report_data['summary']['performance_regressions']}</p>
        </div>
        
        {self._generate_recommendations_html()}
        
        <div class="footer">
            <p><small>Generated by AGENT_GURU Pipeline Reporter v{self.report_data['metadata']['generator_version']}</small></p>
        </div>
    </div>
</body>
</html>
        """
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_file}")
    
    def _generate_recommendations_html(self) -> str:
        """Generate HTML for recommendations section."""
        if not self.report_data['recommendations']:
            return '<div class="recommendations"><h3>✅ No recommendations - all quality gates passed!</h3></div>'
        
        html = '<div class="recommendations"><h3>💡 Recommendations</h3>'
        
        for rec in self.report_data['recommendations']:
            priority_class = f"priority-{rec['priority']}"
            html += f'''
            <div class="recommendation {priority_class}">
                <strong>{rec['category'].title()}</strong> ({rec['priority'].title()} Priority)
                <p>{rec['message']}</p>
                <p><em>Action: {rec['action']}</em></p>
            </div>
            '''
        
        html += '</div>'
        return html
    
    def generate_json_report(self, output_file: Path):
        """Generate JSON report."""
        logger.info(f"Generating JSON report: {output_file}")
        
        with open(output_file, 'w') as f:
            json.dump(self.report_data, f, indent=2)
        
        logger.info(f"JSON report generated: {output_file}")
    
    def generate_reports(self, output_html: Path, output_json: Path):
        """Generate all reports."""
        self.calculate_quality_score()
        self.determine_overall_status()
        self.generate_recommendations()
        
        self.generate_html_report(output_html)
        self.generate_json_report(output_json)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive CI/CD pipeline reports"
    )
    parser.add_argument(
        '--coverage',
        type=str,
        help='Coverage report file (XML or JSON)'
    )
    parser.add_argument(
        '--security',
        type=str,
        help='Security reports directory'
    )
    parser.add_argument(
        '--performance',
        type=str,
        help='Performance reports directory'
    )
    parser.add_argument(
        '--test-results',
        type=str,
        nargs='+',
        help='Test result files (JUnit XML or JSON)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='pipeline-report.html',
        help='Output HTML report file'
    )
    parser.add_argument(
        '--json-output',
        type=str,
        default='pipeline-report.json',
        help='Output JSON report file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create report generator
    generator = PipelineReportGenerator()
    
    # Process coverage report
    if args.coverage:
        generator.process_coverage_report(Path(args.coverage))
    
    # Process security reports
    if args.security:
        generator.process_security_report(Path(args.security))
    
    # Process performance reports
    if args.performance:
        generator.process_performance_report(Path(args.performance))
    
    # Process test results
    if args.test_results:
        test_files = [Path(f) for f in args.test_results]
        generator.process_test_results(test_files)
    
    # Generate reports
    generator.generate_reports(Path(args.output), Path(args.json_output))
    
    # Exit with appropriate code
    status = generator.report_data['summary']['overall_status']
    if status == 'FAILED':
        logger.error("❌ Pipeline quality gates FAILED")
        sys.exit(1)
    elif status == 'WARNING':
        logger.warning("⚠️  Pipeline quality gates passed with WARNINGS")
        sys.exit(0)
    else:
        logger.info("✅ Pipeline quality gates PASSED")
        sys.exit(0)

if __name__ == '__main__':
    main()