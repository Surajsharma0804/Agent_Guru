#!/usr/bin/env python3

"""
AGENT_GURU Coverage Validation Script
Enterprise-grade code coverage analysis with comprehensive reporting
Zero-tolerance quality standards with maximum coverage requirements
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CoverageValidator:
    """Enterprise-grade coverage validation with comprehensive analysis."""
    
    def __init__(self, threshold: int = 100, critical_paths: Optional[List[str]] = None):
        self.threshold = threshold
        self.critical_paths = critical_paths or []
        self.coverage_data = {}
        self.violations = []
        
    def validate_xml_coverage(self, xml_file: Path) -> Dict[str, float]:
        """Validate coverage from XML report (Cobertura format)."""
        logger.info(f"Validating XML coverage report: {xml_file}")
        
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Extract overall coverage
            overall_coverage = float(root.get('line-rate', 0)) * 100
            branch_coverage = float(root.get('branch-rate', 0)) * 100
            
            coverage_data = {
                'overall_line_coverage': overall_coverage,
                'overall_branch_coverage': branch_coverage,
                'packages': {}
            }
            
            # Extract package-level coverage
            for package in root.findall('.//package'):
                package_name = package.get('name', 'unknown')
                package_line_rate = float(package.get('line-rate', 0)) * 100
                package_branch_rate = float(package.get('branch-rate', 0)) * 100
                
                coverage_data['packages'][package_name] = {
                    'line_coverage': package_line_rate,
                    'branch_coverage': package_branch_rate,
                    'classes': {}
                }
                
                # Extract class-level coverage
                for class_elem in package.findall('.//class'):
                    class_name = class_elem.get('name', 'unknown')
                    class_line_rate = float(class_elem.get('line-rate', 0)) * 100
                    class_branch_rate = float(class_elem.get('branch-rate', 0)) * 100
                    
                    coverage_data['packages'][package_name]['classes'][class_name] = {
                        'line_coverage': class_line_rate,
                        'branch_coverage': class_branch_rate
                    }
            
            return coverage_data
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML coverage report: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing coverage report: {e}")
            raise
    
    def validate_json_coverage(self, json_file: Path) -> Dict[str, float]:
        """Validate coverage from JSON report."""
        logger.info(f"Validating JSON coverage report: {json_file}")
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Handle different JSON formats
            if 'totals' in data:
                # pytest-cov format
                totals = data['totals']
                return {
                    'overall_line_coverage': totals.get('percent_covered', 0),
                    'files': data.get('files', {})
                }
            elif 'summary' in data:
                # Other format
                summary = data['summary']
                return {
                    'overall_line_coverage': summary.get('line_coverage', 0),
                    'overall_branch_coverage': summary.get('branch_coverage', 0),
                    'files': data.get('files', {})
                }
            else:
                logger.warning("Unknown JSON coverage format")
                return {}
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON coverage report: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing JSON coverage report: {e}")
            raise
    
    def check_critical_paths(self, coverage_data: Dict) -> List[str]:
        """Check coverage for critical paths."""
        violations = []
        
        for critical_path in self.critical_paths:
            logger.info(f"Checking critical path: {critical_path}")
            
            # Check if critical path is covered
            path_covered = False
            path_coverage = 0.0
            
            # Search in packages/files
            if 'packages' in coverage_data:
                for package_name, package_data in coverage_data['packages'].items():
                    if critical_path in package_name:
                        path_coverage = package_data.get('line_coverage', 0)
                        path_covered = True
                        break
            
            if 'files' in coverage_data:
                for file_name, file_data in coverage_data['files'].items():
                    if critical_path in file_name:
                        if isinstance(file_data, dict):
                            path_coverage = file_data.get('summary', {}).get('percent_covered', 0)
                        else:
                            path_coverage = file_data
                        path_covered = True
                        break
            
            if not path_covered:
                violations.append(f"Critical path '{critical_path}' not found in coverage report")
            elif path_coverage < self.threshold:
                violations.append(
                    f"Critical path '{critical_path}' coverage {path_coverage:.2f}% "
                    f"below threshold {self.threshold}%"
                )
            else:
                logger.info(f"Critical path '{critical_path}' coverage: {path_coverage:.2f}%")
        
        return violations
    
    def validate_coverage_threshold(self, coverage_data: Dict) -> List[str]:
        """Validate overall coverage meets threshold."""
        violations = []
        
        overall_coverage = coverage_data.get('overall_line_coverage', 0)
        branch_coverage = coverage_data.get('overall_branch_coverage', 0)
        
        if overall_coverage < self.threshold:
            violations.append(
                f"Overall line coverage {overall_coverage:.2f}% "
                f"below threshold {self.threshold}%"
            )
        
        if branch_coverage > 0 and branch_coverage < self.threshold:
            violations.append(
                f"Overall branch coverage {branch_coverage:.2f}% "
                f"below threshold {self.threshold}%"
            )
        
        return violations
    
    def generate_coverage_report(self, coverage_data: Dict, output_file: Path):
        """Generate comprehensive coverage report."""
        logger.info(f"Generating coverage report: {output_file}")
        
        report = {
            'timestamp': '2024-01-01T00:00:00Z',  # Would use actual timestamp
            'threshold': self.threshold,
            'critical_paths': self.critical_paths,
            'coverage_summary': {
                'overall_line_coverage': coverage_data.get('overall_line_coverage', 0),
                'overall_branch_coverage': coverage_data.get('overall_branch_coverage', 0),
                'meets_threshold': len(self.violations) == 0
            },
            'violations': self.violations,
            'detailed_coverage': coverage_data
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Coverage report generated: {output_file}")
    
    def validate(self, coverage_files: List[Path]) -> bool:
        """Validate coverage from multiple files."""
        logger.info("Starting coverage validation")
        
        all_coverage_data = {}
        
        for coverage_file in coverage_files:
            if not coverage_file.exists():
                logger.warning(f"Coverage file not found: {coverage_file}")
                continue
            
            try:
                if coverage_file.suffix == '.xml':
                    coverage_data = self.validate_xml_coverage(coverage_file)
                elif coverage_file.suffix == '.json':
                    coverage_data = self.validate_json_coverage(coverage_file)
                else:
                    logger.warning(f"Unsupported coverage file format: {coverage_file}")
                    continue
                
                # Merge coverage data
                for key, value in coverage_data.items():
                    if key in all_coverage_data:
                        if isinstance(value, dict):
                            all_coverage_data[key].update(value)
                        else:
                            # Take the maximum coverage value
                            all_coverage_data[key] = max(all_coverage_data[key], value)
                    else:
                        all_coverage_data[key] = value
                        
            except Exception as e:
                logger.error(f"Failed to process coverage file {coverage_file}: {e}")
                return False
        
        if not all_coverage_data:
            logger.error("No valid coverage data found")
            return False
        
        # Validate coverage thresholds
        threshold_violations = self.validate_coverage_threshold(all_coverage_data)
        self.violations.extend(threshold_violations)
        
        # Check critical paths
        critical_path_violations = self.check_critical_paths(all_coverage_data)
        self.violations.extend(critical_path_violations)
        
        # Generate report
        report_file = Path('coverage-validation-report.json')
        self.generate_coverage_report(all_coverage_data, report_file)
        
        # Log results
        overall_coverage = all_coverage_data.get('overall_line_coverage', 0)
        logger.info(f"Overall line coverage: {overall_coverage:.2f}%")
        
        if self.violations:
            logger.error("Coverage validation failed:")
            for violation in self.violations:
                logger.error(f"  - {violation}")
            return False
        else:
            logger.info("Coverage validation passed")
            return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate code coverage against quality thresholds"
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=100,
        help='Minimum coverage threshold percentage (default: 100)'
    )
    parser.add_argument(
        '--critical-paths',
        type=str,
        help='Comma-separated list of critical paths that must meet threshold'
    )
    parser.add_argument(
        '--coverage-files',
        type=str,
        nargs='+',
        help='Coverage report files to validate'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='coverage-validation-report.json',
        help='Output report file (default: coverage-validation-report.json)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse critical paths
    critical_paths = []
    if args.critical_paths:
        critical_paths = [path.strip() for path in args.critical_paths.split(',')]
    
    # Default coverage files if not specified
    coverage_files = args.coverage_files or [
        'target/tarpaulin-report.xml',
        'coverage.xml',
        'guru/intelligence/coverage.xml'
    ]
    
    # Convert to Path objects
    coverage_file_paths = [Path(f) for f in coverage_files]
    
    # Create validator
    validator = CoverageValidator(
        threshold=args.threshold,
        critical_paths=critical_paths
    )
    
    # Validate coverage
    success = validator.validate(coverage_file_paths)
    
    if success:
        logger.info("✅ Coverage validation PASSED")
        sys.exit(0)
    else:
        logger.error("❌ Coverage validation FAILED")
        sys.exit(1)

if __name__ == '__main__':
    main()